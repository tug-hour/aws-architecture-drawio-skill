# AWS architecture diagrams with draw.io

依頼されたAWS構成を、PPTXの表現規則に沿った編集可能なdraw.io図へ落とすCodexスキルです。スキル名は従来と同じ`aws-architecture-drawio`です。0.8.0では作図判断と必要な既存補助コードへ整理し、独立した別スキルは設置しません。

## 使い方

[SKILL.md](SKILL.md)の指針で配置・文字・接続点・配線を一緒に判断します。新規作成・継続更新は既存の`drawio/1` JSONを更新元とし、[作成と更新](references/authoring.md)のコマンドで原本を生成します。[CaseHub](examples/casehub.json)の配置・内部配線を部品として再利用でき、標準図形をカタログの収録範囲に限定しません。

表示確認は既存draw.ioのCLI書き出しと画像確認を優先します。GUIは原本を開く依頼、直接編集、CLIが使えない場合などに絞ります。確認範囲・再利用条件・コマンドは[作成と更新](references/authoring.md)、PPTXの寸法・色・文字・枠・接続は[表現規則](references/rules.md)を参照してください。通常作図にunitや配布検査を課しません。

JSONは採用した配置・接続点・経由点を保持し、無関係な要素を再配置しません。部品の作成・複製・移動を使え、細かな値も直接編集できます。GUI変更のJSONへの自動同期や、全自動の最適配置は行いません。既存draw.ioだけの直接修正は継続でき、JSON移行を要求しません。公式SVG・外部アイコン画像は埋め込みません。標準図形や矢じりの輪郭はPPTXと近似です。

## 更新と互換性

版番号の定義元は[version.json](references/version.json)です。0.7.0からの更新では既存スキルとローカル変更を退避し、検証したソースを同じ設置名へ置き換えます。追加依存・端末設定・自動更新はありません。設置の更新には利用者の承認が必要です。

`drawio/1`と編集可能なdraw.io原本は継続利用できます。旧`schema_version: "1.0"`、自動配置、プロジェクト形式、ブラウザ計測、厳密照合、旧ZIP生成の入口はこの版に収録しません。これらが必要な場合は保存した0.7.0を使います。旧入力を自動変換せず、既存成果物も変更しません。

開発の確認条件と過去結果の再利用は[development/README.md](development/README.md)にまとめています。

## 使用するもの

外部ソフトウェア・フォントは既存環境を使い、本リポジトリに同梱しません。

| 対象 | 用途・権利情報 |
| --- | --- |
| [Python](https://www.python.org/) | 標準ライブラリによるJSON操作・原本生成・任意の経路診断。[PSF License等](https://docs.python.org/3/license.html) |
| [draw.io Desktop](https://github.com/jgraph/drawio-desktop) | 標準AWS4図形の描画・画像書き出し・編集。参照版32.4.1。Desktopは[GPL-3.0](https://github.com/jgraph/drawio-desktop/blob/v32.4.1/LICENSE)、エディターはApache-2.0、図形は[別条件](https://github.com/jgraph/drawio/blob/v32.4.1/README.md#license) |
| Arial・Arial Unicode MS | 欧文・日本語の表示。利用者が適法に利用できるものを使い、ファイルを配布せずSVGへ埋め込まない |
| [PyYAML](https://github.com/yaml/pyyaml) | 開発時に既存skill-creatorの基本形式検査を使う場合だけ。[MIT](https://github.com/yaml/pyyaml/blob/main/LICENSE)。生成・unitには不要 |

## 参考にしたもの

| 資料 | 利用方法 |
| --- | --- |
| [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/) | Release 23-2026.01.30のLight／Dark PPTXの規則・実測値。[出典とハッシュ](references/provenance.json) |
| [draw.io 32.4.1の標準AWS4](https://github.com/jgraph/drawio/tree/v32.4.1) | 図形ID・名称・寸法等を[カタログ](references/native-catalog.json)へ整理。描画パスやステンシルXMLは同梱しない |
| [LibreOfficeのDrawingML実装](https://github.com/LibreOffice/core/blob/master/oox/source/drawingml/lineproperties.cxx) | 破線比率の解釈を参照。ソースは同梱しない。[ライセンス](https://www.libreoffice.org/licenses/) |
| macOS Quick Look | 過去の元PPTXとの外観比較。PowerPoint本体との描画一致を確認したものではない |

## ライセンス

自作のコード・テスト・構成例・説明は[MIT License](LICENSE)です。第三者の名称・商標・図形・資料や抽出情報へ新たな権利を与えるものではありません。AWSおよびdraw.ioの公式製品、承認・提携を示すものではありません。

カタログに画像・輪郭データは同梱しません。確認済みの事実、適用範囲が未確定の事項、公式条件は[第三者権利の説明](THIRD_PARTY_NOTICES.md)にまとめています。追加許諾や専門家確認を一律の必須条件にはせず、無条件の再配布許諾が確認できたとも扱いません。
