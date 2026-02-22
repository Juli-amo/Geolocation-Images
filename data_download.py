"""
Download YFCC100M training images from AWS S3 (multimedia-commons bucket)
using a CSV of image IDs from scene_M_p_im2gps.csv.

img_id format: <photoid>_<secret>_<serverid>_<owner>.jpg
               e.g. 348532716_5a2b306c86_136_98767940@N00.jpg

S3 Bucket:   s3://multimedia-commons/data/images/
AWS Region:  us-west-2
Registry:    https://registry.opendata.aws/multimedia-commons/

Output format: msgpack shards (identical to original download_images.py)
               Each shard contains dicts: {"image": <jpeg bytes>, "id": <img_id>}

Requirements:
    pip install boto3 msgpack pillow pandas

AWS credentials – replace placeholders below or set via environment variables:
    export AWS_ACCESS_KEY_ID=your_key
    export AWS_SECRET_ACCESS_KEY=your_secret

Usage:
    # Download all images listed in the CSV:
    python download_images_aws.py --img_id_csv resources/mp16_urls.csv

    # Limit to 5 million images with 16 threads:
    python download_images_aws.py --img_id_csv resources/mp16_urls.csv \
        --max_images 5000000 --threads 16

    # Shuffle the image list before downloading:
    python download_images_aws.py --img_id_csv resources/mp16_urls.csv --shuffle
"""

import re
import sys
import time
import hashlib
import logging
from io import BytesIO
from pathlib import Path
from argparse import ArgumentParser
from multiprocessing.pool import ThreadPool
from functools import partial

import boto3
import msgpack
import pandas as pd
import PIL
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

# ---------------------------------------------------------------------------
# AWS configuration – replace with your credentials
# ---------------------------------------------------------------------------
AWS_ACCESS_KEY_ID     = "PLACEHOLDER_ACCESS_KEY_ID"       # <-- replace
AWS_SECRET_ACCESS_KEY = "PLACEHOLDER_SECRET_ACCESS_KEY"   # <-- replace
AWS_REGION            = "us-west-2"

S3_BUCKET       = "multimedia-commons"
S3_IMAGE_PREFIX = "data/images/"


# ---------------------------------------------------------------------------
# MsgPack writer 
# ---------------------------------------------------------------------------

class MsgPackWriter:
    def __init__(self, path, chunk_size=4096):
        self.path = Path(path).absolute()
        self.path.mkdir(parents=True, exist_ok=True)
        self.chunk_size = chunk_size

        shards_re = r"shard_(\d+).msg"
        self.shards_index = [
            int(re.match(shards_re, x.name).group(1))
            for x in self.path.iterdir()
            if x.is_file() and re.match(shards_re, x.name)
        ]
        self.shard_open = None

    def open_next(self):
        next_index = 0 if not self.shards_index else sorted(self.shards_index)[-1] + 1
        self.shards_index.append(next_index)
        if self.shard_open is not None and not self.shard_open.closed:
            self.shard_open.close()
        self.count = 0
        self.shard_open = open(self.path / f"shard_{next_index}.msg", "wb")

    def __enter__(self):
        self.open_next()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shard_open.close()

    def write(self, data):
        if self.count >= self.chunk_size:
            self.open_next()
        self.shard_open.write(msgpack.packb(data))
        self.count += 1


# ---------------------------------------------------------------------------
# S3 key derivation 
# Image Id's from original GeoEstimation Repository available here: https://github.com/Juli-amo/GeoEstimation
# ---------------------------------------------------------------------------

def s3_key_from_img_id(img_id: str) -> str:
    """
    Derive the S3 object key from a YFCC100M img_id.

    img_id format : <photoid>_<secret>_<serverid>_<owner>.jpg
    S3 key format : data/images/<md5[:3]>/<md5[3:6]>/<photoid>_<secret>.jpg

    The S3 bucket organises files by the first 6 hex characters of the MD5
    hash of "<photoid>_<secret>" (without extension). Only photoid and secret
    are used – serverid and owner are metadata-only fields.

    Example:
        img_id  = "348532716_5a2b306c86_136_98767940@N00.jpg"
        base    = "348532716_5a2b306c86"
        md5     = md5("348532716_5a2b306c86")
        s3 key  = "data/images/<md5[:3]>/<md5[3:6]>/348532716_5a2b306c86.jpg"
    """
    stem   = Path(img_id).stem                 
    parts  = stem.split("_")
    photo_id = parts[0]                         
    secret   = parts[1]                         
    filename = f"{photo_id}_{secret}"           

    md5 = hashlib.md5(filename.encode()).hexdigest()
    return f"{S3_IMAGE_PREFIX}{md5[:3]}/{md5[3:6]}/{filename}.jpg"


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def _thumbnail(img: PIL.Image.Image, size: int) -> PIL.Image.Image:
    """Resize maintaining aspect ratio; smaller edge matches 'size'."""
    w, h = img.size
    if w <= size or h <= size:
        return img
    if w < h:
        return img.resize((size, int(size * h / w)), PIL.Image.BILINEAR)
    else:
        return img.resize((int(size * w / h), size), PIL.Image.BILINEAR)


# ---------------------------------------------------------------------------
# Per-image download worker  (runs inside ThreadPool)
# ---------------------------------------------------------------------------

def download_image(img_id: str, s3_client, min_edge_size: int):
    """
    Download one image from S3, resize it, and return a msgpack-ready dict.

    Returns:
        {"image": <jpeg bytes>, "id": <img_id>}  or  None on failure
    """
    s3_key = s3_key_from_img_id(img_id)

    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        raw = response["Body"].read()

        image = Image.open(BytesIO(raw))
        if image.mode != "RGB":
            image = image.convert("RGB")
        if min_edge_size:
            image = _thumbnail(image, min_edge_size)

        fp = BytesIO()
        image.save(fp, "JPEG")
        return {"image": fp.getvalue(), "id": img_id}

    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"Not found on S3: {s3_key}  (img_id={img_id})")
        return None
    except PIL.UnidentifiedImageError as e:
        logger.error(f"Cannot decode {img_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error for {img_id}: {e}")
        return None


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

def load_img_ids(csv_path: Path, max_images: int, shuffle: bool) -> list:
    """
    Read img_ids from a CSV.

    Supports both:
      - scene_M_p_im2gps.csv  (header: img_id, gt_lat, gt_long, ...)
      - mp16_urls.csv          (no header: image_id, url)
    """
    df_peek = pd.read_csv(csv_path, nrows=1)
    if "img_id" in df_peek.columns:
        df = pd.read_csv(csv_path, usecols=["img_id"])
        id_col = "img_id"
    else:
        df = pd.read_csv(csv_path, header=None, names=["img_id", "url"])
        id_col = "img_id"

    df = df.dropna(subset=[id_col])

    if shuffle:
        logger.info("Shuffling image list ...")
        df = df.sample(frac=1, random_state=42)

    df = df.head(max_images)
    logger.info(f"Image IDs loaded from CSV: {len(df)}")
    return df[id_col].tolist()


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    parser = ArgumentParser(
        description="Download YFCC100M images from AWS S3 into msgpack shards."
    )
    parser.add_argument(
        "--img_id_csv",
        type=Path,
        default=Path("resources/mp16_urls.csv"),
        help=(
            "CSV with image IDs. Supports scene_M_p_im2gps.csv (img_id column) "
            "and mp16_urls.csv (no header). Default: resources/mp16_urls.csv"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("resources/images/mp16"),
        help="Output directory for msgpack shards (default: resources/images/mp16)",
    )
    parser.add_argument(
        "--max_images",
        type=int,
        default=5_000_000,
        help="Maximum number of images to download (default: 5000000)",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=16,
        help="Number of parallel download threads (default: 16)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=320,
        help="Resize so the shorter edge = SIZE pixels (default: 320)",
    )
    parser.add_argument(
        "--shuffle",
        action="store_true",
        help="Shuffle the image list before downloading",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    # --- S3 client ---
    s3 = boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    logger.info(f"Connected to S3 bucket '{S3_BUCKET}' in {AWS_REGION}")

    # --- Load image IDs ---
    img_ids = load_img_ids(args.img_id_csv, args.max_images, args.shuffle)
    total   = len(img_ids)

    if total == 0:
        logger.error("No image IDs found in CSV – check the file path and format.")
        return 1

    logger.info(
        f"Starting download: {total} images | "
        f"threads={args.threads} | output={args.output}"
    )

    # --- Thread pool download ---
    worker = partial(download_image, s3_client=s3, min_edge_size=args.size)

    counter_successful = 0
    counter_failed     = 0
    start = time.time()

    with ThreadPool(args.threads) as pool:
        with MsgPackWriter(args.output) as writer:
            for i, result in enumerate(pool.imap_unordered(worker, img_ids)):
                if result is not None:
                    writer.write(result)
                    counter_successful += 1
                else:
                    counter_failed += 1

                if (i + 1) % 1000 == 0:
                    elapsed = time.time() - start
                    rate    = 1000 / elapsed
                    pct     = (i + 1) / total * 100
                    logger.info(
                        f"[{i+1}/{total}] ({pct:.1f}%)  "
                        f"{rate:.1f} img/s | "
                        f"OK: {counter_successful} | "
                        f"Failed: {counter_failed}"
                    )
                    start = time.time()

    logger.info(
        f"Finished. Downloaded: {counter_successful} | "
        f"Failed: {counter_failed} | "
        f"Total: {counter_successful + counter_failed}/{total}"
    )
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("YFCC100M_Downloader")
    logger.setLevel(logging.INFO)

    fh = logging.FileHandler(str(args.output / "writer.log"))
    fh.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)

    sys.exit(main())