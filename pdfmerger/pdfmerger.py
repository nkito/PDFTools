# 
# * 環境設定
# 
#  $ python3 -m venv _pdf
#  $ _pdf\script\activate
#  $ pip install pyside6 pypdf2 reportlab pyinstaller
#
# * 使用方法
#
#  $ python pdfmerger.py
# 
# * 単独で動く実行形式の生成
#
#  $ pyinstaller --onefile --noconsole pdfmerger.py 
#    (distフォルダ内にバイナリができる)
#
# 以下は LLM 生成コード

import sys
import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QListWidget,
    QPushButton, QLineEdit, QLabel, QFileDialog, QAbstractItemView, QMenu
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from PyPDF2 import PdfMerger, PdfReader
from reportlab.pdfgen import canvas
import tempfile

class PdfListWidget(QListWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)

        # 並び替え（内部移動）
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QAbstractItemView.InternalMove)

        # ★ 複数選択（必要なければ SingleSelection のままでもOK）
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # ★ 右クリックメニューを有効化
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_context_menu)

    # --- 右クリックメニュー ---
    def open_context_menu(self, pos):
        item = self.itemAt(pos)  # 右クリック位置のアイテム
        menu = QMenu(self)

        delete_action = QAction("削除", self)
        delete_action.setEnabled(item is not None)  # 空白部分を右クリックしたら無効
        delete_action.triggered.connect(self.delete_selected_items)

        menu.addAction(delete_action)
        menu.exec(self.mapToGlobal(pos))

    def keyPressEvent(self, event):
        # Delete / Backspace で選択項目を削除
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected_items()
            event.accept()
            return
        super().keyPressEvent(event)

    def delete_selected_items(self):
        # 選択中アイテムを全削除（後ろから消すのが安全）
        rows = sorted({idx.row() for idx in self.selectedIndexes()}, reverse=True)
        for r in rows:
            self.takeItem(r)

    # --- D&D（並び替えと外部追加の両立） ---
    def dragEnterEvent(self, event):
        if event.source() is self:
            event.accept()
        elif event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        # 内部ドラッグ（並び替え）はQtに任せる
        if event.source() is self:
            super().dropEvent(event)
            return

        # 外部PDFの追加
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith(".pdf"):
                    self.addItem(path)

        event.acceptProposedAction()
      
class PdfMergeApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF連結ツール")
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        self.list = PdfListWidget()
        # self.list.setDragDropMode(QAbstractItemView.InternalMove)

        layout.addWidget(QLabel("PDFファイル一覧（ドラッグで追加 / 並べ替え）"))
        layout.addWidget(self.list)

        self.output_edit = QLineEdit("merged.pdf")
        layout.addWidget(QLabel("出力ファイル名"))
        layout.addWidget(self.output_edit)

        blank_btn = QPushButton("空白ページを挿入")
        blank_btn.clicked.connect(self.add_blank_page)
        layout.addWidget(blank_btn)

        merge_btn = QPushButton("PDFを連結")
        merge_btn.clicked.connect(self.merge_pdf)
        layout.addWidget(merge_btn)

    def add_blank_page(self):
        self.list.addItem("【空白ページ】")

    def create_blank_pdf(self):
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        c = canvas.Canvas(temp.name)
        c.showPage()
        c.save()
        return temp.name

    def merge_pdf(self):
        if self.list.count() == 0:
            return

        merger = PdfMerger()
        blank_files = []

        for i in range(self.list.count()):
            item = self.list.item(i).text()
            if item == "【空白ページ】":
                blank = self.create_blank_pdf()
                blank_files.append(blank)
                merger.append(blank)
            else:
                merger.append(item)

        output_path = QFileDialog.getSaveFileName(
            self, "保存先を選択", self.output_edit.text(), "PDF Files (*.pdf)"
        )[0]

        if output_path:
            merger.write(output_path)
            merger.close()

        for f in blank_files:
            os.remove(f)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PdfMergeApp()
    w.show()
    sys.exit(app.exec())
