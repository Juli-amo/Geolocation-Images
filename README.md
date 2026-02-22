# Geolocation-Images

> Ein Deep-Learning-System, das den Aufnahmeort eines Fotos allein anhand seines Bildinhalts schätzt – ohne GPS-Metadaten, ohne Landmarken-Datenbank.

**Universitätsprojekt** | Hochschule Düsseldorf · Advances in Intelligent Systems · Julia Moor  
Basierend auf: [Müller-Budack et al., ECCV 2018](https://openaccess.thecvf.com/content_ECCV_2018/papers/Eric_Muller-Budack_Geolocation_Estimation_of_ECCV_2018_paper.pdf)

---

## Inhalt

- [Über das Projekt](#über-das-projekt)
- [Wie es funktioniert](#wie-es-funktioniert)
- [Installation](#installation)
- [GUI](#gui-starten)
- [Projektstruktur](#projektstruktur)
- [Quellen](#quellen)

---

## Über das Projekt

Dieses Projekt implementiert ein hierarchisches Klassifikationssystem zur Geolokalisierung von Fotos. Das Modell teilt die Erde in geografische Zellen ein (basierend auf der [S2 Geometry Library](https://code.google.com/archive/p/s2-geometry-library/)) und klassifiziert ein Eingabebild auf drei Auflösungsebenen gleichzeitig: grob, mittel und fein. Durch die Kombination aller drei Ebenen über eine Hierarchie entsteht eine robustere Vorhersage.

Im Gegensatz zu herkömmlichen Retrieval-Ansätzen, die eine riesige Referenzdatenbank benötigen, reicht hier ein einziges trainiertes CNN-Modell zur Vorhersage.

<img width="2074" height="1532" alt="Image" src="https://github.com/user-attachments/assets/0119c1b0-ac5e-449d-91b3-65d95a2b792b" />
---

## Wie es funktioniert

Das System basiert auf einem **ResNet50**-Backbone, das auf dem **MP-16**-Datensatz (~5 Millionen geo-getaggte Fotos aus der AWS-Datenbank) trainiert wurde.

Die Erde ist in drei Partitionierungen aufgeteilt:

| Partitionierung | Zellen | Granularität |
|---|---|---|
| Coarse | ~1.000 | Kontinent / Großregion |
| Middle | ~2.000 | Land / Großstadt |
| Fine | ~5.000 | Stadt / Region |

<img width="392" height="156" alt="Image" src="https://github.com/user-attachments/assets/549d7585-56d9-4488-8217-4631fd7e7673" />

Für jedes Eingabebild werden **5 Crops** (FiveCrop) erzeugt, durch das Modell geleitet und die Ergebnisse gemittelt. Die finale Koordinate wird über die Hierarchie-Vorhersage bestimmt.

---

## Installation

**Voraussetzung:** CUDA 12.4, Python 3.10, conda

```bash
git clone https://github.com/Juli-amo/Geolocation-Images.git
cd Geolocation-Images
```

PyTorch zuerst installieren:

```bash
pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 \
    --index-url https://download.pytorch.org/whl/cu124
```

Alle weiteren Abhängigkeiten:

```bash
pip install -r requirements.txt
```

---

## GUI starten

Das Projekt enthält eine grafische Oberfläche, über die beliebige Fotos hochgeladen und die vorhergesagte Position auf einer interaktiven Weltkarte angezeigt werden kann.

```bash
python frontend/gui.py
```

Die GUI lädt beim Start automatisch das Modell aus `models/base_M/`. Nach dem Hochladen eines Bildes und Klick auf **„Standort vorhersagen"** erscheint der geschätzte Standort als roter Marker auf der Karte.

---

## Projektstruktur

```
├── backend/
│   ├── classification/
│   │   ├── dataset.py          
│   │   ├── train_base.py       
│   │   ├── inference.py        
│   │   ├── test.py             
│   │   ├── s2_utils.py         
│   │   └── utils_global.py    
│   ├── config/
│   │   └── baseM.yml           
│   └── partitioning/
│       ├── assign_classes.py   
│       └── create_cells.py     
├── frontend/
│   └── gui.py                  
├── data_download.py            
├── environment.yml             
├── requirements.txt           
├── scene_M_p_im2gps.csv        
├── .gitignore
└── README.md
```

---

## Quellen

**Paper:**
> Eric Müller-Budack, Kader Pustu-Iren, Ralph Ewerth:
> *"Geolocation Estimation of Photos using a Hierarchical Model and Scene Classification"*.
> European Conference on Computer Vision (ECCV), Munich, 2018, pp. 575–592.
> [PDF](https://openaccess.thecvf.com/content_ECCV_2018/papers/Eric_Muller-Budack_Geolocation_Estimation_of_ECCV_2018_paper.pdf)

**Original Repository:**
> [https://github.com/TIBHannover/GeoEstimation](https://github.com/TIBHannover/GeoEstimation)

---

*Dieses Projekt wurde im Rahmen des Moduls „Advances in Intelligent Systems" an der Hochschule Düsseldorf erstellt.*
