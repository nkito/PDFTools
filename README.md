# PDFTools

PDFTools は、複数の PDF を結合したり、PDF からページを抽出・並び替えたりするためのプログラム集です。
本リポジトリでは、ソースコードに加えて、Windows 用の実行ファイル（ビルド済み）も配布しています。

## 機能

### PDFMerger
- 複数の PDF ファイルを 1 つの PDF に結合
- GUI（グラフィカルユーザーインターフェース）による操作が可能

### PDFPagePicker
- PDF ファイルからマウスで必要なページを選択して新しい PDF を作成
- 選択したページの順序を変更することも可能
- GUI（グラフィカルユーザーインターフェース）による操作

## インストール方法

### ビルド済み実行ファイルを使用する場合（Windows）

1. [Releases](https://github.com/yourusername/PDFTools/releases) ページにアクセスします。
2. 最新の Windows 用リリースをダウンロードします。
3. ダウンロードしたアーカイブを展開します。
4. 実行ファイル（`pdfmerger.exe` または `pdfpagepicker.exe`）を起動します。

### ソースコードから実行する場合

1. リポジトリをクローンします：
   ```bash
   git clone https://github.com/yourusername/PDFTools.git
   ```
2. プロジェクトディレクトリに移動します：
   ```bash
   cd PDFTools
   ```
3. 必要な依存関係をインストールします：
   ```
   pip install -r requirements.txt
   ```
4. 使用したいスクリプトを実行します：
   ```bash
   python pdfmerger.py
   ```
   または
   ```bash
   python pdfpagepicker.py
   ```

