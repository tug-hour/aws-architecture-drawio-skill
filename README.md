# AWS architecture diagrams with draw.io

PPTXの描画規則を参照し、draw.io標準AWS図形で編集可能なAWS構成図を作るCodexスキルです。通常は原本を直接作成・編集し、必要なテーマとSVG・PNGだけを出力します。公式SVGは埋め込みません。

AWSおよびdraw.ioの公式製品ではなく、承認・提携を示すものではありません。標準図形の輪郭や矢じりはPPTXと完全一致しません。

## 利用と確認

1. [SKILL.md](SKILL.md)の基本手順で、依頼された構成を描きます。図形は過去の検証済み一覧に限定しません。
2. [rendering.md](references/rendering.md)に従い、一度表示して日本語・接続・枠・使った図形を確認します。独自JSON、ブラウザ計測、再書き出し検査、開発テストは通常作図の必須条件ではありません。
3. 大きな構成の配置調整には、任意の[配置表・経由点生成](references/layout-and-routing.md)を使えます。JSONからの再生成や厳密な照合を必要とする場合は、既存の生成・検証ツールも使えます。

版番号は[version.json](references/version.json)、PPTXの規則は[aws-rules.md](references/aws-rules.md)を参照してください。[verified-assets.json](references/verified-assets.json)は確認済み範囲の記録です。未確認の図形は使用した図で確認し、全図形を検証済みとは扱いません。

スキル開発時の回帰検証・配布確認は通常作図と分け、条件とコマンドをrendering.mdにまとめています。機械検査は図の意味やAWS構成の正しさを保証しません。

## 使用するもの

通常の直接作図にはdraw.ioを使います。Pythonは補助スクリプト、Node.js・Playwright・Chromiumは任意の計測・厳密検証に使います。次のソフトウェア・フォントは利用者の既存環境を参照します。リポジトリと配布ZIPには同梱しません。検証済みの版は[rendering.md](references/rendering.md)に記載しています。

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
