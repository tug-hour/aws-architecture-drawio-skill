# AWS architecture diagrams with draw.io

draw.io標準AWS図形を使い、日本語のAWS構成図を作成・検証するCodexスキルです。編集可能な`.drawio`原本と、ライト・ダーク両テーマのSVG・PNGを生成します。公式SVGは埋め込みません。

AWSおよびdraw.ioの公式製品ではなく、両者の承認・提携を示すものではありません。PPTXの寸法・配色・ラベル規則を参照していますが、標準図形の輪郭や矢じりまで完全一致するものではありません。

## 利用と検証

版番号は[version.json](references/version.json)、対応済み記号は[verified-assets.json](references/verified-assets.json)を参照してください。

1. [SKILL.md](SKILL.md)で対応範囲と入力の作り方を確認します。
2. [rendering.md](references/rendering.md)で既存の実行環境・専用profile・フォントの参照先を指定します。依存の自動導入は行いません。
3. 同文書の「スキルの生成物用の検証」にあるコマンドで、新規出力先へ生成し、同じ実行の両テーマ画像を目視確認します。

開発用unitは生成物検証の代用ではありません。変更時に行う検証とZIP生成の条件・コマンドも[rendering.md](references/rendering.md)に集約しています。Mac arm64以外の環境や別フォントは未検証です。生成物の機械検査に合格しても、図の意味や読みやすさ、AWSの承認を保証するものではありません。

## 使用するもの

次のソフトウェア・フォントは利用者の既存環境を参照します。リポジトリと配布ZIPには同梱しません。検証済みの版は[rendering.md](references/rendering.md)に記載しています。

| 対象 | 用途・権利情報 |
| --- | --- |
| [draw.io Desktop](https://github.com/jgraph/drawio-desktop) | 標準AWS4図形による描画・書き出し。Desktopは[GPL-3.0](https://github.com/jgraph/drawio-desktop/blob/v32.4.1/LICENSE)、エディターのコードはApache-2.0、図形は[別条件](https://github.com/jgraph/drawio/blob/v32.4.1/README.md#license) |
| [Python](https://www.python.org/) | 生成・検証・配布処理。PSF License等の[同梱ライセンス](https://docs.python.org/3/license.html) |
| [Node.js](https://nodejs.org/)・[Playwright](https://playwright.dev/)・[Chromium](https://www.chromium.org/) | 文字幅計測、ブラウザでの検証・画像確認。Node.jsは[MITおよび第三者ライセンス](https://github.com/nodejs/node/blob/v24.19.0/LICENSE)、Playwrightは[Apache-2.0](https://github.com/microsoft/playwright/blob/main/LICENSE)、ブラウザは[Chromiumのライセンスと第三者条件](https://github.com/chromium/chromium/blob/main/LICENSE) |
| Arial・Arial Unicode MS | 欧文・日本語の計測と表示。利用者が適法に利用できるフォントを指定。フォントファイルを配布せず、出力SVGへの埋め込みも無効化 |
| [PyYAML](https://github.com/yaml/pyyaml) | 開発時のSKILL.md形式検査のみ。[MIT](https://github.com/yaml/pyyaml/blob/main/LICENSE)。図の生成・通常unitには不要 |

## 参考にしたもの

| 資料 | 参照箇所・利用方法 |
| --- | --- |
| [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/) | Release 23-2026.01.30のLight／Dark PPTXを、寸法・色・ラベル・枠・接続の規則と実測値の基準に使用。原資料のファイル名・ハッシュは[provenance.json](references/provenance.json)、規則は[aws-rules.md](references/aws-rules.md) |
| [draw.io 32.4.1](https://github.com/jgraph/drawio/tree/v32.4.1)に付属する標準AWS4図形 | 図形ID・名称・既定寸法を[native-catalog.json](references/native-catalog.json)へ整理。描画パスやステンシルXML自体は同梱しない |
| [LibreOfficeのDrawingML実装](https://github.com/LibreOffice/core/blob/master/oox/source/drawingml/lineproperties.cxx) | `sysDash`と`dash`の線幅比の解釈を参照。ソースファイルは同梱しない。参照元は[MPL-2.0等](https://www.libreoffice.org/licenses/) |
| macOS Quick Look | 元PPTXとの外観比較に使用。PowerPoint本体での描画一致を確認したものではない |

## ライセンス

本プロジェクトの自作コード・テスト・構成例・説明文は[MIT License](LICENSE)です。MITは、本プロジェクトが権利を持つ部分に適用します。第三者の名称・商標・図形・資料や、それらから抽出した情報について、本プロジェクトが新たな権利を与えるものではありません。

カタログは、既存図形を指定するためのID・名称・寸法・色などの参照情報と設定表です。画像や図形の輪郭データは同梱していません。確認した公式条件から、このカタログの配布に追加許諾が必須とは断定できていません。一方、AWSの利用契約の適用範囲と、情報集合として保護される部分の有無は未確定です。

確認済みの事実と未確定事項は[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)に分けて記載しています。追加許諾の取得や専門家への確認を一律の公開条件にはしません。具体的に適用される条件と配布内容に応じて判断し、実際に許諾が必要な利用ではその条件に従います。

公開候補の範囲と履歴・個人情報の扱いは[一般公開用の候補と公開判断](references/release-operations.md#一般公開用の候補と公開判断)を参照してください。
