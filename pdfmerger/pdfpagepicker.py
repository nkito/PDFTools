# 
# * 環境設定
# 
#  $ python3 -m venv _pdf
#  $ _pdf\script\activate
#  $ pip install pyside6 pymupdf
#
# * 使用方法
#
#  $ python pdfpagepicker.py
# 
# * 単独で動く実行形式の生成
#
#  $ pyinstaller --onefile --noconsole pdfpagepicker.py
#    (distフォルダ内にバイナリができる)
#
# 以下は LLM 生成コード

import sys
import os
import json
from dataclasses import dataclass

from PySide6.QtCore import Qt, QSize, QMimeData, QByteArray
from PySide6.QtGui import QAction, QIcon, QPixmap, QImage, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QFileDialog,
    QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem, QSplitter,
    QMessageBox, QAbstractItemView, QMenu
)

import fitz  # PyMuPDF


MIME_TYPE = "application/x-pdf-page-items"


@dataclass(frozen=True)
class PageRef:
    src_path: str
    page_index: int  # 0-based


def render_thumbnail(doc: fitz.Document, page_index: int, max_side_px: int = 220) -> QIcon:
    """PDFの1ページをサムネイルとしてレンダリングし、QIconを返す。"""
    page = doc.load_page(page_index)
    rect = page.rect
    # 長辺が max_side_px になるようスケール
    scale = max_side_px / max(rect.width, rect.height)
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    # pix.samples: RGB bytes
    fmt = QImage.Format_RGB888
    img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
    pm = QPixmap.fromImage(img)
    return QIcon(pm)


class ThumbListWidget(QListWidget):
    """
    左右のサムネイル一覧で共通利用するリスト。
    - 左: DragOnly（右へコピー）
    - 右: DragDrop（内部移動で並び替え + 外部からドロップで追加）
    """
    def __init__(self, parent=None, allow_external_drop=False, allow_internal_reorder=False):
        super().__init__(parent)
        self.allow_external_drop = allow_external_drop
        self.allow_internal_reorder = allow_internal_reorder

        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(180, 180))
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Snap)
        self.setSpacing(10)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setUniformItemSizes(True)

        self.setDragEnabled(True)
        self.setAcceptDrops(allow_external_drop or allow_internal_reorder)
        self.setDropIndicatorShown(True)

        if allow_internal_reorder:
            # 内部移動による並び替え
            self.setDragDropMode(QAbstractItemView.InternalMove)
            self.setDefaultDropAction(Qt.MoveAction)
        else:
            # 左側はドラッグのみ（コピー用途）
            self.setDragDropMode(QAbstractItemView.DragOnly)

        if allow_external_drop:
            self.setDragDropMode(QAbstractItemView.DragDrop)
            self.setDefaultDropAction(Qt.CopyAction)

    def keyPressEvent(self, event):
        # 右側で Delete キー削除を効かせる（右側のみで利用想定）
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self._delete_selected_items()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        # 右クリックメニュー（右側のみで利用想定）
        menu = QMenu(self)
        act_del = QAction("削除", self)
        act_del.setShortcut(QKeySequence.Delete)
        act_del.triggered.connect(self._delete_selected_items)
        menu.addAction(act_del)

        if self.allow_internal_reorder or self.allow_external_drop:
            menu.exec(event.globalPos())
        else:
            # 左側はメニュー不要
            super().contextMenuEvent(event)

    def _delete_selected_items(self):
        # 選択アイテムを削除（右側想定）
        rows = sorted([self.row(it) for it in self.selectedItems()], reverse=True)
        for r in rows:
            self.takeItem(r)

    def startDrag(self, supportedActions):
        items = self.selectedItems()
        if not items:
            return

        refs = []
        for it in items:
            ref = it.data(Qt.UserRole)
            if isinstance(ref, PageRef):
                refs.append({"src_path": ref.src_path, "page_index": ref.page_index})

        if not refs:
            return

        mime = QMimeData()
        payload = json.dumps(refs, ensure_ascii=False).encode("utf-8")
        mime.setData(MIME_TYPE, QByteArray(payload))

        # ドラッグ中の見た目
        drag_icon = items[0].icon()
        pm = drag_icon.pixmap(160, 160)

        from PySide6.QtGui import QDrag
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(pm)
        drag.setHotSpot(pm.rect().center())

        # 左→右はコピー、右内部は移動、右→右(外部)などは状況に応じて
        if self.allow_internal_reorder:
            drag.exec(Qt.MoveAction | Qt.CopyAction, Qt.MoveAction)
        else:
            drag.exec(Qt.CopyAction, Qt.CopyAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE) and self.allow_external_drop:
            event.acceptProposedAction()
        elif self.allow_internal_reorder:
            super().dragEnterEvent(event)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE) and self.allow_external_drop:
            event.acceptProposedAction()
        elif self.allow_internal_reorder:
            super().dragMoveEvent(event)
        else:
            event.ignore()

    def dropEvent(self, event):
        # 右側で左からのドロップを受けて追加する
        if event.mimeData().hasFormat(MIME_TYPE) and self.allow_external_drop:
            data = bytes(event.mimeData().data(MIME_TYPE))
            try:
                refs = json.loads(data.decode("utf-8"))
            except Exception:
                event.ignore()
                return

            # ドロップ位置の行
            drop_pos = event.position().toPoint()
            target_item = self.itemAt(drop_pos)
            insert_row = self.row(target_item) if target_item else self.count()

            for i, ref in enumerate(refs):
                pr = PageRef(ref["src_path"], int(ref["page_index"]))
                # 元のアイコンを再利用したいが、ここでは簡便に「同じ情報だけ」持たせる
                # （アイコンは MainWindow 側で作る）
                it = QListWidgetItem(f"p.{pr.page_index + 1}")
                it.setData(Qt.UserRole, pr)
                self.insertItem(insert_row + i, it)

            event.acceptProposedAction()
            return

        # 内部移動（並び替え）は標準処理に任せる
        if self.allow_internal_reorder:
            super().dropEvent(event)
            return

        event.ignore()


class PdfDropLabel(QLabel):
    """左側のドロップ領域（PDFをここへドロップ）"""
    def __init__(self, on_pdf_dropped, parent=None):
        super().__init__(parent)
        self.on_pdf_dropped = on_pdf_dropped
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setText("ここにPDFをドラッグ＆ドロップ\n（左側にページサムネイルを表示）")
        self.setStyleSheet(
            "QLabel{border:2px dashed #888; padding:18px; color:#444;}"
        )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            # PDFのみ許可
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith(".pdf") and os.path.isfile(path):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            return
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf") and os.path.isfile(path):
                self.on_pdf_dropped(path)
                event.acceptProposedAction()
                return


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDFページ抽出ツール（サムネ選択・並び替え・削除）")
        self.resize(1200, 720)

        self.src_doc = None
        self.src_path = None
        self.thumb_cache = {}  # page_index -> QIcon

        root = QWidget()
        self.setCentralWidget(root)

        self.left_drop = PdfDropLabel(self.load_pdf)
        self.left_list = ThumbListWidget(allow_external_drop=False, allow_internal_reorder=False)
        self.right_list = ThumbListWidget(allow_external_drop=True, allow_internal_reorder=True)

        self.left_title = QLabel("左：PDF全ページ（ドラッグで右へ追加）")
        self.right_title = QLabel("右：出力するページ（並び替え・削除可）")

        self.btn_export = QPushButton("PDF出力…")
        self.btn_clear_right = QPushButton("右側を全消去")
        self.btn_clear_right.clicked.connect(self.right_list.clear)
        self.btn_export.clicked.connect(self.export_pdf)

        # レイアウト
        left_panel = QWidget()
        left_v = QVBoxLayout(left_panel)
        left_v.addWidget(self.left_title)
        left_v.addWidget(self.left_drop)
        left_v.addWidget(self.left_list, 1)

        right_panel = QWidget()
        right_v = QVBoxLayout(right_panel)
        right_v.addWidget(self.right_title)
        right_v.addWidget(self.right_list, 1)

        bottom_bar = QWidget()
        bottom_l = QHBoxLayout(bottom_bar)
        bottom_l.addWidget(self.btn_clear_right)
        bottom_l.addStretch(1)
        bottom_l.addWidget(self.btn_export)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([560, 640])

        layout = QVBoxLayout(root)
        layout.addWidget(splitter, 1)
        layout.addWidget(bottom_bar)

        # 左→右へドラッグした時、アイコンが無いと寂しいので
        # 右側に追加されたアイテムに対して、後でアイコンを付与する仕掛け
        self.right_list.model().rowsInserted.connect(self.on_right_rows_inserted)

        # 左側のアイテムをダブルクリックでも右に追加（便利機能）
        self.left_list.itemDoubleClicked.connect(self.add_to_right_from_left)

    def load_pdf(self, path: str):
        try:
            doc = fitz.open(path)
        except Exception as e:
            QMessageBox.critical(self, "読み込みエラー", f"PDFを開けませんでした。\n{e}")
            return

        # 状態初期化
        self.src_doc = doc
        self.src_path = path
        self.thumb_cache.clear()

        self.left_drop.setText(f"読み込み中：{os.path.basename(path)}")
        QApplication.processEvents()

        self.left_list.clear()
        self.right_list.clear()

        # 全ページ分のサムネを生成して表示
        # ※ページが非常に多い場合は「遅延生成（lazy）」にすると快適です（後述）
        for i in range(doc.page_count):
            icon = render_thumbnail(doc, i, max_side_px=220)
            self.thumb_cache[i] = icon

            it = QListWidgetItem(f"p.{i+1}")
            it.setIcon(icon)
            it.setData(Qt.UserRole, PageRef(path, i))
            self.left_list.addItem(it)

        self.left_drop.setText(f"読み込み完了：{os.path.basename(path)}（{doc.page_count}ページ）")

    def add_to_right_from_left(self, item: QListWidgetItem):
        # 左側ダブルクリックで右に追加
        ref = item.data(Qt.UserRole)
        if not isinstance(ref, PageRef):
            return
        it = QListWidgetItem(f"p.{ref.page_index + 1}")
        it.setData(Qt.UserRole, ref)
        self.right_list.addItem(it)
        # アイコンは rowsInserted シグナルで付与

    def on_right_rows_inserted(self, parent, first, last):
        # 右側に追加されたアイテムに、対応するサムネアイコンを付与
        for row in range(first, last + 1):
            it = self.right_list.item(row)
            if not it:
                continue
            ref = it.data(Qt.UserRole)
            if isinstance(ref, PageRef) and ref.src_path == self.src_path and self.src_doc:
                icon = self.thumb_cache.get(ref.page_index)
                if icon is None:
                    icon = render_thumbnail(self.src_doc, ref.page_index, max_side_px=220)
                    self.thumb_cache[ref.page_index] = icon
                it.setIcon(icon)

    def export_pdf(self):
        if self.src_doc is None or self.src_path is None:
            QMessageBox.information(self, "未読み込み", "まず左側にPDFをドラッグ＆ドロップして読み込んでください。")
            return
        if self.right_list.count() == 0:
            QMessageBox.information(self, "ページ未選択", "右側に出力したいページを追加してください。")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存先を選択", "output.pdf", "PDF Files (*.pdf)"
        )
        if not save_path:
            return

        try:
            out = fitz.open()  # new empty PDF
            # 右側の順番通りにページを追加
            for i in range(self.right_list.count()):
                it = self.right_list.item(i)
                ref = it.data(Qt.UserRole)
                if not isinstance(ref, PageRef):
                    continue
                # 1ページずつ挿入（確実に互換）
                out.insert_pdf(self.src_doc, from_page=ref.page_index, to_page=ref.page_index)

            out.save(save_path)
            out.close()
        except Exception as e:
            QMessageBox.critical(self, "保存エラー", f"PDFの保存に失敗しました。\n{e}")
            return

        QMessageBox.information(self, "完了", f"保存しました：\n{save_path}")


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()