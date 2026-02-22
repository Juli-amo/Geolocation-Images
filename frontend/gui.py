"""
GeoCLIP GUI - SIMPLIFIED
Nur AI Prediction auf Weltkarte
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from geoclip import GeoCLIP
import folium
import tempfile


class PredictionThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, model, image_path):
        super().__init__()
        self.model = model
        self.image_path = image_path
    
    def run(self):
        try:
            top_pred_gps, top_pred_prob = self.model.predict(self.image_path, top_k=1)
            result = {
                'latitude': float(top_pred_gps[0][0]),
                'longitude': float(top_pred_gps[0][1]),
                'probability': float(top_pred_prob[0])
            }
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class GeoCLIPApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.model = None
        self.current_image_path = None
        self.prediction_data = None
        
        self.init_ui()
        self.load_model()
    
    def init_ui(self):
        self.setWindowTitle('GeoCLIP - Geoestimation Predictions')
        self.setGeometry(100, 100, 1400, 900)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        
        # Left Panel
        left_panel = QWidget()
        left_panel.setMaximumWidth(400)
        left_panel.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2a2a2a, stop:1 #1a1a1a);
                border-radius: 8px;
            }
        """)
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        
        # Header
        header = QLabel('Bild hochladen')
        header.setFont(QFont('Segoe UI', 14, QFont.Weight.Bold))
        header.setStyleSheet('color: #ffffff; padding: 10px; background: transparent;')
        left_layout.addWidget(header)
        
        # Upload Button
        self.upload_btn = QPushButton('Bild auswählen')
        self.upload_btn.setMinimumHeight(50)
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #9fa4b8, stop:1 #b8aec4);
                color: #000000;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8a8fa3, stop:1 #a89eb4);
            }
        """)
        self.upload_btn.clicked.connect(self.upload_image)
        left_layout.addWidget(self.upload_btn)
        
        # Image Preview
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(350)
        self.image_label.setMinimumWidth(350)
        self.image_label.setStyleSheet("""
            QLabel {
                border: 2px solid #9fa4b8;
                border-radius: 8px;
                background-color: rgba(42, 42, 42, 0.5);
                color: #ffffff;
            }
        """)
        self.image_label.setText('Kein Bild ausgewählt')
        left_layout.addWidget(self.image_label)
        
        # Predict Button
        self.predict_btn = QPushButton('AI Standort vorhersagen')
        self.predict_btn.setMinimumHeight(45)
        self.predict_btn.setEnabled(False)
        self.predict_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #9fa4b8, stop:1 #b8aec4);
                color: #000000;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8a8fa3, stop:1 #a89eb4);
            }
            QPushButton:disabled {
                background: #3a3a3a;
                color: #666666;
            }
        """)
        self.predict_btn.clicked.connect(self.predict_location)
        left_layout.addWidget(self.predict_btn)
        
        # Result
        self.result_text = QTextEdit()
        self.result_text.setMaximumHeight(150)
        self.result_text.setReadOnly(True)
        self.result_text.setStyleSheet("""
            QTextEdit {
                background-color: #3a3a3a;
                border: 1px solid #9fa4b8;
                border-radius: 8px;
                padding: 10px;
                color: #ffffff;
                font-size: 12px;
            }
        """)
        self.result_text.hide()
        left_layout.addWidget(self.result_text)
        
        # Clear Button
        self.clear_btn = QPushButton('Zurücksetzen')
        self.clear_btn.setMinimumHeight(40)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(58, 58, 58, 0.8);
                color: #ffffff;
                border: 2px solid #9fa4b8;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(70, 70, 70, 1);
                border-color: #b8aec4;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_all)
        self.clear_btn.hide()
        left_layout.addWidget(self.clear_btn)
        
        # Status
        self.status_label = QLabel('Lade Modell...')
        self.status_label.setStyleSheet('color: #ffffff; padding: 10px; background: transparent;')
        left_layout.addWidget(self.status_label)
        
        left_layout.addStretch()
        
        # Map
        self.map_view = QWebEngineView()
        self.map_view.setMinimumWidth(800)
        
        settings = self.map_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        
        self.update_map()
        
        main_layout.addWidget(left_panel)
        main_layout.addWidget(self.map_view, stretch=1)
        
        self.setStyleSheet("QMainWindow { background-color: #1a1a1a; }")
    
    def load_model(self):
        try:
            self.status_label.setText('Lade Modell...')
            QApplication.processEvents()
            self.model = GeoCLIP()
            self.status_label.setText('Modell geladen!')
            self.status_label.setStyleSheet('color: #27ae60; padding: 10px; background: transparent;')
        except Exception as e:
            self.status_label.setText(f'Fehler: {str(e)}')
            self.status_label.setStyleSheet('color: #e74c3c; padding: 10px; background: transparent;')
    
    def upload_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Bild auswählen', '', 'Bilder (*.png *.jpg *.jpeg *.bmp)')
        
        if file_path:
            self.current_image_path = file_path
            pixmap = QPixmap(file_path)
            
            # EXIF fix
            from PIL import Image
            try:
                pil_image = Image.open(file_path)
                if hasattr(pil_image, '_getexif') and pil_image._getexif():
                    orientation = pil_image._getexif().get(274)
                    if orientation == 3:
                        pil_image = pil_image.rotate(180, expand=True)
                    elif orientation == 6:
                        pil_image = pil_image.rotate(270, expand=True)
                    elif orientation == 8:
                        pil_image = pil_image.rotate(90, expand=True)
                    temp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                    pil_image.save(temp.name)
                    pixmap = QPixmap(temp.name)
            except:
                pass
            
            self.image_label.setPixmap(pixmap.scaled(350, 350, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.predict_btn.setEnabled(True)
            self.clear_btn.show()
            self.status_label.setText(f'Bild: {Path(file_path).name}')
    
    def predict_location(self):
        if not self.current_image_path or not self.model:
            return
        
        self.status_label.setText('Analysiere...')
        self.predict_btn.setEnabled(False)
        QApplication.processEvents()
        
        self.prediction_thread = PredictionThread(self.model, self.current_image_path)
        self.prediction_thread.finished.connect(self.on_prediction_finished)
        self.prediction_thread.error.connect(self.on_prediction_error)
        self.prediction_thread.start()
    
    def on_prediction_finished(self, result):
        self.prediction_data = result
        
        self.result_text.setHtml(f"""
            <h3 style='color: #ffffff;'>AI Prediction</h3>
            <p style='color: #ffffff;'><strong>Lat:</strong> {result['latitude']:.6f}</p>
            <p style='color: #ffffff;'><strong>Lng:</strong> {result['longitude']:.6f}</p>
        """)
        self.result_text.show()
        
        self.update_map()
        
        self.predict_btn.setEnabled(True)
        self.status_label.setText('Fertig!')
        self.status_label.setStyleSheet('color: #27ae60; padding: 10px; background: transparent;')
    
    def on_prediction_error(self, error_msg):
        self.status_label.setText(f'Fehler: {error_msg}')
        self.status_label.setStyleSheet('color: #e74c3c; padding: 10px; background: transparent;')
        self.predict_btn.setEnabled(True)
    
    def update_map(self):
        m = folium.Map(location=[20, 0], zoom_start=2, min_zoom=1, tiles='OpenStreetMap', zoom_control=True, scrollWheelZoom=True)
        
        if self.prediction_data:
            folium.CircleMarker(
                location=[self.prediction_data['latitude'], self.prediction_data['longitude']],
                radius=15,
                color='#ffffff',
                weight=3,
                fillColor='#e74c3c',
                fillOpacity=0.9,
                popup=f"<strong>GeoCLIP</strong><br>{self.prediction_data['latitude']:.4f}, {self.prediction_data['longitude']:.4f}"
            ).add_to(m)
        
        map_html = m.get_root().render()
        
        fix_js = """
        <script>
        var check = setInterval(function() {
            if (typeof map !== 'undefined' && typeof L !== 'undefined') {
                clearInterval(check);
                map.setView([20, 0], 2, {animate: false});
                setTimeout(function() { map.setView([20, 0], 2); }, 200);
            }
        }, 100);
        </script>
        """
        
        map_html = map_html.replace('</body>', fix_js + '</body>')
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(map_html)
            self.map_view.setUrl(QUrl.fromLocalFile(f.name))
    
    def clear_all(self):
        self.current_image_path = None
        self.prediction_data = None
        self.image_label.clear()
        self.image_label.setText('Kein Bild ausgewählt')
        self.result_text.hide()
        self.predict_btn.setEnabled(False)
        self.clear_btn.hide()
        self.update_map()
        self.status_label.setText('Zurückgesetzt.')


def main():
    app = QApplication(sys.argv)
    window = GeoCLIPApp()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
    