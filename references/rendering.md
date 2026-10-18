# 描画と確認

## スキルの生成物用の検証

通常作図は、依頼された図をdraw.ioで一度表示して確認する。日本語・使った記号・ラベルの切れ・重なり・接続方向・枠の所属を見て、必要な箇所だけ直す。指定テーマだけを作り、両テーマを納品する場合だけ両方を見る。図の小さな変更に、全カタログや無関係な図の検査を追加しない。

新規作成は全体と主要経路を確認する。改修は同じ原本・スタイル・描画環境の確認済み結果を使い、変更点と移動・配線の影響が及ぶ周辺を確認する。PPTXとの照合では、使った記号の寸法・色、12ptのアイコン／接続ラベル、サービス名の改行、枠と矢印を確認する。「前の図と同じ」は適合の証明ではない。図の題名・節見出しとアイコン／接続ラベルは区別する。文字領域を小さくしただけで重なりが解消したとは判断しない。

独自JSON、ブラウザ実測、画像の再書き出し照合、検査レポート、unit、全受け入れ検証は必須ではない。原本を直接編集した場合も、元JSONとの一致を納品条件にしない。画像が必要ならdraw.ioの画面または既存CLIで一度書き出し、その同じ画像を確認する。

CLIの一例（既存draw.ioと既存の専用profileを使い、新しい出力ファイルを指定する）：

```sh
test ! -e "<new-diagram.svg>" &&
"<drawio>" --disable-update --user-data-dir="<dedicated-profile>" --export --format svg --theme light --embed-svg-fonts false --output "<new-diagram.svg>" "<diagram.drawio>"
```

PNGが必要ならformatをpngにし、SVG用のembed-svg-fonts指定を外す。原本の背景・配色は固定し、mxGraphModelにadaptiveColors="none"を指定する。CLIのtheme lightはエディター側の色変換を防ぐための指定であり、暗い背景の原本もその色で書き出す。

## 原本の経路候補を比較する場合

交差・迂回・文字との重なりが調整を難しくしている場合だけ使う。既存Pythonの標準ライブラリだけで読み取り、描画・図の変更・設定変更は行わない。候補ごとに別名で保存した原本を渡す。1ファイルでも確認でき、比較のための独自JSONや全候補の書き出しは不要である。

```sh
python3 -B <skill-dir>/scripts/drawio_routes.py <before.drawio> <candidate.drawio>
```

保存された直交経路・接続点とセルの文字領域を使い、`routing.py`の衝突・再侵入・線分共有・端点直線・接触・包含枠通過の判定を再利用する。各線の衝突等は最初の指摘を返す。座標・距離はpt。結果には原本のSHA-256、ページごとの解析した接続ID、交差・折れ曲がり・長さ、指摘、未解析要素を返す。指摘は確認補助であり、終了コード0は読み取り・解析を実行できたことだけを示す。読み取り不能は2。既存の生成・厳密検証の判定と終了コードは変えない。

ロックや接続不可の指定だけでは、アイコン・図形を障害物から除外しない。背景として除外するのは、頂点の子ではない最背面の矩形で、全要素を囲み、ページ背景と同色・枠線なし・文字なし・接続不可で、線の端点にもなっていないものだけとする。包含枠と非表示のグループ、線自身の端点とその文字を持たない装飾子は従来どおり除外し、文字は障害物に残す。

CLIの通常出力はセルごとの`topology`を省略し、比較結果・経路ID・数値・指摘・未解析部分を残す。内部比較データが必要な場合だけ、上のコマンドに`--details`を付ける。Pythonの`inspect_xml`・`compare`の返却内容は維持する。

`same_topology`はセルID・親・接続先・矢印の指定、`same_route_coverage`は解析した接続IDの一致を示す。どちらかがfalseなら、接続欠落や未解析部分を減点せずに数値だけで優劣を決めない。一致しても意味・色・図形・文字の一致や適合の証明ではない。

文字領域は保存されたセル寸法であり、実際の改行・フォントの計測ではない。プレーンテキストの保存高さが明示された文字サイズ×行数より小さい場合は、はみ出しの可能性を`unresolved`へ記録する。これは下限との比較であり、指摘がないことも実際の文字領域の正しさを保証しない。原本や障害物の寸法は自動変更しない。自動経路、曲線、回転、図形周囲への接続点投影、枠への接続、子を持たず包含・横断の意味が不明な枠、線に追従する文字などは推測せず`unresolved`に残す。キャンバス境界は検査しない。この解析範囲を図形の使用制限にしない。原本全体の数値は周辺への影響の確認に使い、警告ゼロや数値最小を完成条件にしない。

配置と経路の候補を絞ってから、採用する図を上記の生成物用手順で表示する。変更した経路、その接続点・矢じり、周辺の文字と交差を確認し、候補の比較ごとに再描画しない。未変更部分は同じ原本・スタイル・描画環境に対する既存の目視結果を再利用できるが、移動で線や文字が近づいた範囲は変更範囲に含める。

## 配置表を使う場合

大きな図の配置・配線を反復調整する場合だけ使う。基本は既存Pythonの標準ライブラリで原本を生成する。入力と配置表の形式は[配置と経路](layout-and-routing.md)を参照する。

```sh
python3 -B <skill-dir>/scripts/waypoints.py --input <architecture.json> --spec <placement.spec.py> --output <new-dir>
```

原本と、経由点を保存したarchitecture.json、layout.json、report.jsonが残る。status=authoredは原本生成、measurement=estimatedは推定文字幅を意味し、描画確認済みという意味ではない。レーンを直しても、元の入力と以前の出力は変えない。

既存ブラウザでの文字幅計測が必要ならruntimeを追加する。SVG・PNGも必要ならexportとprofileを追加する。どちらも必須ではない。

```sh
python3 -B <skill-dir>/scripts/waypoints.py --input <architecture.json> --spec <placement.spec.py> --output <new-dir> --runtime <runtime.json> --export --profile <dedicated-profile>
```

exportはテーマごとにSVG・PNGを一度書き出す。status=exportedでも目視確認は別である。交差などの警告は確認補助であり、ゼロ件にするためだけの作り直しはしない。接続ラベルや構造を変更する必要がある場合は原本を直接編集してもよい。

## 任意の厳密な生成物検証

JSONからの再生成、原本と入力の一致、再描画の再現性を確認したい場合だけ既存のrun.pyを使う。複数図の網羅を機械検査したい場合はproject.pyを使う。以下は通常作図の必須手順ではない。

```sh
python3 -B <skill-dir>/scripts/run.py --input <architecture.json> --output <new-dir> --profile <dedicated-profile> --runtime <runtime.json>
python3 -B <skill-dir>/scripts/project.py --input <project.json> --output <new-project-dir> --profile <dedicated-profile> --runtime <runtime.json>
```

生成処理は仮領域で完了した後に新規出力先へ渡す。原本のセル・標準図形・接続・親子・配置を入力から再構成したモデルと照合する。SHA-256で入力・配置・計測・原本・SVG・PNG・生成レポートの組を確認し、原本からSVG・PNGを新しく再描画する。保存済みSVGの構造とPNGのハッシュが新描画と一致することを検査してから、ブラウザで描画する。

保存ハッシュは混入・変更の検出に使う。署名や悪意ある改ざんへの認証ではない。元の依頼JSONとの照合は一括実行で行う。生成フォルダと依頼の両方を変更した場合に、以前の意図を推定することはない。

AZ名の重複省略は[AZ所属の表示](service-labels-and-conformance.md#az所属の表示)に従い、完成した図の枠とラベルを目視で確認する。W_AZ_LABEL_REDUNDANTとW_AZ_LABEL_MISMATCHは確認候補であり、機械検査がこの作図方針への適合を判定したとは扱わない。旧入力の名称エラーは[移行案内](service-labels-and-conformance.md#互換性)を参照する。

経路確定後の`W_EDGE_FRAME_TRANSIT`は、両端の所属枠・祖先枠を除く包含枠の内部通過を示す。横断グループ枠や境界に触れるだけの線分は対象外とし、接続と枠の組ごとに該当線分をまとめる。`W_EDGE_CONTACT`は異なる接続の曲がり角・線分端での接触を示す。同じ位置の交差・線分重複・両接続の端点同士の接触は既存検査に任せ、同じ接触点は重複して報告しない。線分番号は0始まりで、接触座標は最終レイアウトのpt値である。

これらは意味や読みやすさを確認するための警告であり、入力拒否・経路変更・生成物検証の不合格条件には追加しない。プロジェクトの`operational_quality`は要確認とする。枠の内部通過と枠沿いの近接は異なる観点なので、両方に該当すれば各警告を記録する。必要な迂回か、接触が接続と誤読されるか、枠の境界に意味の誤解がないかは目視で判断する。既存の距離・迂回閾値は読みやすさの補助基準であり、PPTXの必須数値規則とは扱わない。

`W_FRAME_OVERLAP`は、最終配置で祖先関係のない包含枠同士に面積のある重なりがあることを示す。親子を含む全ての祖先関係、横断枠、境界・角に触れるだけの組は除外する。枠の組ごとに一件とし、両方のIDと重なり領域の最終座標・寸法を`details.overlap_rect_pt`へpt値で記録する。共通の親を持つ兄弟枠は対象とする。これは所属の見え方を確認する補助であり、入力拒否・自動配置変更・生成物の合否・運用品質の判定・終了コードは変更しない。既存の無関係なノードの包含エラー、横断枠の共有境界警告、接続の内部通過・接触・近接検査は維持する。

検査対象はラベル・用語集の内容、寸法、実使用フォント、色、記号、枠・破線、矢じり、接続のアイコン貫通・ラベル衝突・線分重複・キャンバス外へのはみ出し、両背景の配置一致、画像の非埋め込み。全ての交差や枠境界の意味、構成の技術的妥当性は検証しない。

プロジェクトCLIの最終出力の`presentation`とビューアは、既存レポートの判定結果を表示用に読み替える。個別ビューの生成・検証が失敗した場合は「生成・検証失敗」、生成物の検査が成功して運用品質が要確認の場合は「要確認」、機械検査が合格した場合は目視確認が必要であることを表示する。判定情報が不足している場合は「結果未確認」とする。ビューID・警告やエラーのコード・要素ID・理由を表示し、警告を再判定しない。失敗・未確認のビューでは、画像・SVGと編集原本へのリンク・テーマと拡大操作・図の確認案内・省略接続の案内を隠す。ビュー選択と判定理由は残し、機械検査合格または要確認のビューに戻すと図専用の操作と案内を復元する。既存の`status`と終了コードは維持し、要確認でもプロジェクト全体は従来どおり`failed`・終了コード2となる。

失敗時もresult.jsonと可能な検査レポートを保存する。検査失敗時はブラウザPNGを完成品として公開しない。既存の出力先は拒否する。成功したdraftはproduction_eligible=falseであり、正式運用の合格ではない。

分離実行はbuild_drawio.pyとverify_native.py。verify_native.pyにも--drawio・--profile・--runtimeを渡す。--expected-inputで元の構成JSONを指定できる。原本だけを手修正した図は、この生成物の照合で失敗する。JSON・手動座標・経由点を更新して再生成する。

## 計測・厳密検証の既存環境

現行版の対応環境（版番号は[version.json](version.json)）：Mac arm64、draw.io Desktop 32.4.1、Python 3.9.6、Node.js 24.19.0、Playwright 1.64.0、Chrome Headless Shell 155.0.8059.39。欧文Arial、日本語Arial Unicode MSを使用する。他OS・別フォントは未検証。

runtime JSONは以下の形で、すべて既存ファイルへの絶対パスを指定する。

```json
{
  "node": "/absolute/path/to/node",
  "playwright_module": "/absolute/path/to/node_modules/playwright",
  "browser_executable": "/absolute/path/to/chrome-headless-shell",
  "fonts": {
    "latin": "/absolute/path/to/Arial.ttf",
    "japanese": "/absolute/path/to/Arial Unicode.ttf"
  }
}
```

`doctor.py --runtime <runtime.json>`はファイルとバージョンを読み取り確認し、アプリを起動せず設定を変更しない。実際の描画の成功とは区別する。新規導入・更新には事前の安全確認とユーザー承認が必要。プログラムは自動インストールを行わない。

Macのdraw.io既定パスは/Applications/draw.io.app/Contents/MacOS/draw.io。--drawioで変更できる。--profileには専用領域を必ず明示する。draw.io呼び出しには--disable-updateを付け、SVGフォント埋め込みを無効にする。背景と色は図内で指定し、書き出しの--theme lightで自動色変換を避ける。ブラウザ検証はネットワークを遮断し、サンドボックスを有効にする。

## 既存環境を使う場合

本書のコマンドでは、プレースホルダーを利用環境の絶対パスに置き換える。パスに空白がある場合は引用符で囲む。成功を確認済みの環境では同じ参照先を再利用する。

| コマンド中の指定 | 指定するもの |
| --- | --- |
| `python3` | 対応バージョンを満たす既存Pythonの実行ファイル |
| `<skill-dir>` | スキルの設置先。更新候補の検証時は、その作業用コピー |
| `<runtime.json>` | 既存の実行成功環境を記録したruntime JSON |
| `<dedicated-profile>` | 同じ環境で使用したdraw.io専用profile |
| `<yaml-site-packages>` | 既存の隔離済みPyYAMLのsite-packages |
| `<quick-validate.py>` | 既存のskill-creatorにある`scripts/quick_validate.py` |

任意のブラウザ計測・厳密検証で環境を初めて使う場合、参照先が変わった場合、または起動失敗を調べる場合は、アプリを起動しない次の確認を行う。runtime・専用profile・実行ファイルが存在しない場合は停止し、自動作成・再導入・別環境への切替は行わない。doctorの成功は実描画の合格を意味しない。

```sh
test -d "<dedicated-profile>" &&
python3 -B "<skill-dir>/scripts/doctor.py" --runtime "<runtime.json>"
```

### 既存PyYAMLによるスキル形式検査

開発用のSKILL.md形式検査には、隔離済みのPyYAML 6.0.3を使う。通常のPythonで`import yaml`が失敗しても、新規導入が必要とは判断しない。次の指定はこのコマンドだけに適用し、シェル設定やグローバル環境へ保存しない。通常の描画・unitにPyYAML用の設定は不要である。

```sh
test -f "<yaml-site-packages>/yaml/__init__.py" &&
PYTHONPATH="<yaml-site-packages>" python3 -B "<quick-validate.py>" "<skill-dir>"
```

参照先の欠落・読み込み失敗は形式検査の実行不可として記録し、スキルの不合格と区別する。形式検査の合格は、コード・描画・図の意味の検証を代替しない。

### draw.ioの実行環境の選択

サンドボックス内のdraw.io起動が`SIGABRT`・`_RegisterApplication`で失敗し、同じアプリ・runtime・専用profileによる通常ターミナル実行で成功することを確認済みの場合は、同条件の失敗を繰り返さず、承認された通常ターミナルから下記の生成物用コマンド、または開発用の対象コマンドを実行する。通常作図では、操作可能な既存draw.io画面で開く・書き出す方法も使える。開いたファイル名と保存先を確認し、別ファイルや未保存のユーザー作業を上書きしない。画面操作も使えない場合、またはCLIによる厳密検証が必要な場合は、入力・新規出力先・対象範囲を確定したコマンドを利用者へ渡す。

成功時と同じ参照先を使い、専用profileを共有する描画は直列に実行する。再開用スクリプトを使う場合も、対象ソースと新規出力先を確認する。環境確認だけのために成功済みの図を再描画せず、必要な検証を新規出力先へ一度実行し、同じ生成物で目視確認まで行う。アプリの再導入、署名・隔離属性の変更、OS保護機能の無効化を起動失敗への対処として自動実行しない。

## スキル開発用の検証

スキルの実装・構成例の変更による回帰を調べる。テスト用入力や意図的に不正にした成果物を使い、検出処理も確認する。利用者の個々の図を検証した結果とは区別する。

変更内容と影響範囲に応じて次の検証を選ぶ。配布・導入だけを理由に全受け入れ検証を追加しない。実行条件とコマンドは本書を定義元とし、同じ観点を確認済みの検査は重ねて実行しない。

| 変更内容 | 開発用の検証範囲 |
| --- | --- |
| 文書・版管理情報のみ | 内容、参照リンク、SKILL.mdの基本形式、版と配布manifestの整合性。描画・回帰テストは追加しない |
| 構成例のみ | その例に関係するunitと、変更した例の生成・両テーマの目視。JSON生成・照合ツール用の例は任意の厳密検証、配置表の例は配置表コマンドを使う |
| 生成・検証コード、処理が参照する規則やカタログ | unit。図形一覧の定義・生成・照合に影響する場合は一覧の整合性も確認する。実描画への影響がある場合は該当するnativeを実行する |
| テストのみ | 変更したテストを`--match`で実行する。共通fixtureやテスト選択・実行処理を変更した場合は、その影響を受ける範囲も含める |
| ZIPの収集対象・同梱文書だけの変更 | 下記の配布用検査。生成・検証処理が不変なら描画は追加しない |
| 生成・検証処理を広く変更し、対象を絞った確認では足りない場合 | 下記の全受け入れ検証と、生成した両テーマの目視 |

### 経路補助の変更

`drawio_routes.py`の読取・診断と明示接続点は、小さな独立構成を使う`test_drawio_routes`・`test_waypoints`で確認する。入れ子座標・全文字領域・過小な文字高さ・未解析部分・線分共有・配置入替による交差低減、ロックされた図形の衝突と背景・装飾の除外、簡潔なCLI出力での指摘保持と入力非変更を対象にする。通常unitに含まれるため、unit完了後に同じテストを単独で再実行しない。開発中に対象だけを実行する場合は既存test_runnerの`--match test_drawio_routes`または`--match test_waypoints`を使う。

読み取り専用の診断だけの変更では再描画しない。共通経路処理を変更する場合は通常unitで従来の生成・失敗条件を確認し、描画される経路が変わる場合だけ、その例の指定テーマを表示する。大きな既存図は調整効果の任意比較に使い、通常unitへ取り込まない。改善時間を比較する場合は同じ構成・環境で作図と描画に要した時間、描画回数を記録し、解析時間だけを作図時間の短縮として報告しない。

### 導入・更新時の確認

利用する機能と変更の影響範囲だけを確認する。通常の直接作図では、新しい確認用の図を一度表示すればよく、ブラウザ計測や全開発テストは不要である。JSON補助ツールを使う場合はその機能の確認を選び、厳密な照合が必要な場合だけrun.py・project.pyを使う。変更していない既存図を、スキルの更新だけを理由に再生成しない。

描画結果を再利用する場合は、対象入力・配置表・描画に関係するコードと規則・実行環境が確認時と同じで、生成と目視が完了した記録を参照する。文書やテストだけの変更なら再描画を追加しない。記録には対象版・コミットと今回の差分を示し、過去の結果を現行版で再実行したとは扱わない。配布物の確認は[ZIPの同梱確認](#zipの同梱確認)に従う。

### 構成例・配置・警告の変更

プロジェクトの一部ビューの配置だけを変更した場合は、`project.project_views()`で正本全体の参照・必須経路・ビュー網羅を確認し、変更したビューの`architecture`を新規JSONへ保存する。そのJSONを上記の単独図用コマンドで生成・検証し、`quality.operational_quality()`で元ビューの`display`に対する表示品質も確認する。対象ビューID、正本のハッシュ、保存先、結果を記録し、全ビューの描画検証とは区別する。枠同士や見出しとの重なりも両テーマで目視し、経路警告がないことだけで配置を合格としない。モデルや共通設定も変更した場合は、その影響先を対象に含める。

Web図の配置変更では、変更した地域のビュー（`t-web`または`o-web`）だけを上記の一部ビュー用手順で生成・検証し、同じ出力の両テーマを目視する。両地域に影響するモデル・共通設定・共通処理の変更、または両地域の比較を依頼された場合は、両方を対象にする。比較対象として描画する地域の構成は変更しない。API→DynamoDB接続が両AZのDBサブネット内部を通らず、無関係な包含枠が重ならないことを確認する。標準図形・寸法・配色・線幅・矢じり・通信方向を維持し、実測した文字幅で決まる経路とラベルの余白を確認する。

通常unitの`test_web_state_access_avoids_database_subnets`は、現行構成の両地域を推定文字幅で検査する。旧配置への置換は行わず、生成物の検証・目視の代用にはしない。旧東京配置での検出確認は、このテストまたは内部通過警告の追加・検出判定の変更時、および下記の再現手順を変更したときだけ、下記コマンドで別途行う。配置だけの変更や、再現手順に影響しない文書更新では、確認済みの旧配置検査を繰り返さない。

通常unitの`RouteAdvisoryTests`は小さな独立構成を使い、旧東京配置やプロジェクト構成例を読み込まない。旧配置の別検査では入力をメモリ上だけで変更し、同じレイアウト計算から、既存のDBサブネット通過検査の失敗と内部通過警告の両方を確認する。終了コード0はこの2点を確認できたことを意味し、旧配置の合格ではない。通常unitとは分けて結果を記録する。

```sh
python3 -B - <skill-dir> <<'PY'
import sys, unittest
from unittest.mock import patch
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(root / 'scripts'), str(root / 'tests')]
from test_semantics_project import ProjectTests
from layout import layout

class OldTokyoLayout(ProjectTests):
    def setUp(self):
        super().setUp()
        view = next(v for v in self.p['views'] if v['id'] == 't-web')
        next(p for p in view['layout']['positions'] if p['node_id'] == 'tdbb')['x_pt'] = 980

observed = []
def capture(*args, **kwargs):
    lay, warnings = layout(*args, **kwargs)
    observed.extend(warnings)
    return lay, warnings

result = unittest.TestResult()
with patch('test_semantics_project.layout', side_effect=capture):
    OldTokyoLayout('test_web_state_access_avoids_database_subnets').run(result)
if result.errors or len(result.failures) != 1 or 'AssertionError: True is not false : tdbsubb' not in result.failures[0][1]:
    raise SystemExit('failed: expected DB subnet crossing was not detected; inspect the reproducer and test')
if not any(w['code'] == 'W_EDGE_FRAME_TRANSIT' and w['element_ids'] == ['tstateaccess','tdbsubb'] for w in observed):
    raise SystemExit('failed: expected frame transit warning was not detected')
print('passed: old Tokyo crossing detected by regression assertion and advisory (separate from normal unit)')
PY
```

描画、SVG・PNGの書き出し、原本や再描画結果の照合、ブラウザ検査など、生成物の作成・検証処理に影響する変更はnativeの対象とする。これらの処理が参照する色・寸法・フォント・接続などの規則やカタログを変更する場合も含む。例えば、verify_native.pyで不一致を拒否する処理の変更は、描画コードが同じでも実描画による異常系テストで確認する。

描画前に差分レビューとunitを完了する。警告の判定条件だけの変更は、警告内容・入力非変更・合否非変更・描画モデル非変更をunitで確認できれば、実描画を追加しない。警告の保存・受け渡しや生成処理も変更する場合は、影響するnativeテストを実行する。凡例の表示・定義順・配置に影響する変更もnativeの対象とする。

描画前に拒否する原本の図形・接続先・親要素の不一致や、SVG改変・記号削除によるハッシュ不一致は、`ArtifactValidationTests`へ集約し、描画処理が呼ばれないこともunitで確認する。この検出のためだけに実描画の入力を作らない。ハッシュを書き換えた古いSVG・PNGを再描画結果との比較で拒否する検査は、異なる検出段階のためnativeに残す。テストの統合・削除だけで生成・検証処理が不変なら、通常unitと検査対象の引き継ぎ確認に絞る。

経路確認警告の変更では、下記の通常unitに含まれる`RouteAdvisoryTests`で内部通過・接触の検出と除外条件、重複抑制、入力・経路・両テーマの描画モデル非変更、運用品質の要確認判定を確認する。警告の保存・受け渡し処理を変更しなければ、この条件だけを理由にnativeを追加しない。既存事例への影響を確認する場合は、保存済みの`architecture.json`と`layout.json`を読み取り、`routing.review_warnings(architecture, layout['edges'], layout['groups'])`の増分を確認する。参照元と警告を新規の結果ファイルへ記録し、保存済み成果物へ書き戻さない。この読み取り確認は新たな描画・目視の合格を意味しない。

包含枠の重なり警告を変更した場合は、通常unitの`FrameAdvisoryTests`で検出・除外・一組一件の報告、最終座標、入力・配置・両テーマの描画モデル・運用品質・プロジェクト終了コードの不変を確認する。警告の保存・受け渡しを変更しない限り、この変更だけを理由にnativeやブラウザ表示確認、旧東京配置の別検査を追加しない。既存のWeb図の回帰テストは通常unit内で実行する。

保存済みの配置への影響を確認する場合は、次の読み取り検査を使う。対象フォルダには`architecture.json`と`layout.json`が必要で、複数指定できる。結果には入力のハッシュ、参照元、警告、実行時間を記録する。元ファイルへ書き戻さず、旧版の生成物に対する新たな生成物検証・目視の合格とも扱わない。

```sh
python3 -B - <skill-dir> <new-result.json> <saved-diagram-dir> [<saved-diagram-dir> ...] <<'PY'
import hashlib, json, sys, time
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'scripts'))
from layout import frame_overlap_warnings
from version import get_version
start = time.monotonic()
output = Path(sys.argv[2])
if output.exists():
    raise SystemExit('Existing output')
records = []
for directory in map(Path, sys.argv[3:]):
    source = {name: (directory / name).read_bytes() for name in ('architecture.json', 'layout.json')}
    architecture = json.loads(source['architecture.json'])
    frames = json.loads(source['layout.json'])['groups']
    records.append({'source': str(directory.resolve()),
                    'sha256': {name: hashlib.sha256(data).hexdigest() for name, data in source.items()},
                    'warnings': frame_overlap_warnings(architecture, frames)})
result = {'scope': 'saved-layout advisory inspection; no rendering', 'version': get_version(),
          'output': str(output.resolve()), 'records': records, 'seconds': round(time.monotonic()-start, 6)}
with output.open('x') as stream:
    stream.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
PY
```

関連nativeテスト内でrun.pyによる両テーマの生成・生成物検証が完了し、変更した条件を確認できる場合は、別の代表構成を重ねて生成しない。開発用のテスト結果と、その実行内の生成物用レポートを区別して記録する。目視が必要なら同じ実行の生成物を保持して確認する。追加実行は、選んだテストで確認できない観点がある場合に限る。利用者が別途作成する図には、冒頭の通常作図の確認を適用する。

PPTXとの比較は、寸法・配色・フォント・輪郭・矢じりを区別して記録する。描画設定を変更しなければ、全記号の比較図や全構成例の再描画は追加しない。標準図形であることや内部検査の合格だけでPPTX準拠とは判定しない。

通常unit（検証済み一覧の整合性確認を含む）：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -B <skill-dir>/scripts/test_runner.py --group unit --output <new-unit-dir>
```

同じソースで通常unitが全件合格した場合、`SupportIndexTests.test_installed_index_matches_the_catalog`で整合性も確認済みのため、単独の整合性検査は省略する。`tests-summary.json`の`status=passed`、`group=unit`、`match=null`と`source_binding`を確認する。

上記の変更内容別条件で整合性確認が必要で、通常unitを実行していない場合、または`--match`でこのテストを除外した場合だけ、次を実行する。対象テストを含む絞り込み実行が合格し、ソースも同一なら単独検査は省略できる。単独検査の合格でunitの失敗・未実行を補ったとは扱わない。文書・版管理情報のみの変更では、どちらも追加しない。

```text
python3 -B <skill-dir>/scripts/verified_assets.py
```

nativeは承認済みの実描画環境で実行する。環境の選択は上記の手順に従う。

```text
AWS_NATIVE_DRAWIO_RUNTIME=<runtime.json> AWS_DRAWIO_PROFILE=<dedicated-profile> PYTHONDONTWRITEBYTECODE=1 python3 -B <skill-dir>/scripts/test_runner.py --group native --output <new-native-dir>
```

`--group all`は両群を実行する。unitとnativeの全件を同じソース・環境で完了した場合は、allを重ねて実行しない。`--match <test-idの一部>`は対象を絞る。実描画が必要なのに環境がない場合はunavailableで終了し、skipを成功に数えない。従来のunittest discoverも利用できるが、環境変数がない場合は実描画テストをskipする。

目視確認や失敗調査に生成物を使う場合は、対応テストを選んで`--keep-artifacts`を付ける。保持対応は各テストの`supports_artifacts=True`で宣言する。影響する対象を`--match`で選ぶ。この保持処理自体を変更する場合は、unitと対応テスト一件を実行し、終了後に保存先と生成物を確認する。

```text
AWS_NATIVE_DRAWIO_RUNTIME=<runtime.json> AWS_DRAWIO_PROFILE=<dedicated-profile> PYTHONDONTWRITEBYTECODE=1 python3 -B <skill-dir>/scripts/test_runner.py --group native --match AdvisoryNativeTests --keep-artifacts --output <new-native-dir>
```

矢じりの種類・サイズを変更する場合は、unitで旧設定との差が矢じり設定だけであることを確認し、次の関連nativeテストを実行する。片方向・双方向・無矢印、水平・垂直の終端とアイコンへの接続を同じ図で確認する。保存した両テーマを目視し、線幅・色・方向・経路と矢じり周辺の余白を確認する。PPTXとの比較済み候補を採用するだけなら、候補比較図は再生成しない。

```text
AWS_NATIVE_DRAWIO_RUNTIME=<runtime.json> AWS_DRAWIO_PROFILE=<dedicated-profile> PYTHONDONTWRITEBYTECODE=1 python3 -B <skill-dir>/scripts/test_runner.py --group native --match ArrowNativeTests --keep-artifacts --output <new-native-dir>
```

保持先は新規出力先内の`artifacts/<選択テストの通し番号>`。tests-summary.jsonの`artifacts`に、実際に作成したディレクトリの絶対パスとテストIDを記録する。ここで案内する対応テストの生成物用レポートは保持先の`out/result.json`、目視対象は`out/qa/light.browser.png`と`out/qa/dark.browser.png`。同じ実行のレポートと画像を使い、確認のためだけに再生成しない。

保持指定がなければ、従来どおり一時生成物を削除する。保持指定時は失敗時の調査用出力も残すが、保存されたことを検証成功や目視確認済みの根拠にしない。未対応テストを一つでも選ぶと、実行前に`E_ARTIFACT_RETENTION_UNSUPPORTED`で失敗する。既存の出力先・保持先は上書きしない。

各実行はtests-summary.jsonへ選択範囲、ソースのハッシュ、終了コード、実行時間、各テストの時間を保存する。全体時間には準備・終了処理を含む。個別テストの時間にはクラス単位の準備・終了処理を含まない。失敗した対象を再実行する場合は新しい出力先を使い、初回の失敗記録を残す。自動再試行、依存の導入、設定変更は行わない。

### 結果表示だけを変更した場合

判定・生成・警告の保存処理が不変で、CLIやビューアの表示だけを変更した場合は、通常unitと次のブラウザ表示確認を行う。既存の両テーマのPNG・SVG・draw.io原本・architecture.jsonがある生成フォルダを`<saved-diagram-dir>`に指定する。検査は新規出力先へ画像などをコピーし、表示確認用の合格・要確認・失敗・未確認レポートを作る。元の成果物は変更せず、図の再描画も行わない。

```text
python3 -B <skill-dir>/tests/check_review_viewer.py --runtime <runtime.json> --source <saved-diagram-dir> --output <new-viewer-check-dir>
```

状態の切替、警告・要素ID、文字列の安全な表示を確認する。失敗・未確認の各ビューから合格・要確認の各ビューへ切り替え、上記の図専用操作と案内の非表示・復元、画像とリンクの参照先、復元後の拡大操作を確認する。`browser-check.json`に結果と時間を保存し、同じ出力先の`light.viewer.png`・`dark.viewer.png`・`failed.viewer.png`・`unknown.viewer.png`を目視する。この表示確認は新たな図の生成物検証ではない。判定・生成処理にも変更が及ぶ場合は、上記の変更内容別の検証条件を適用する。

### 記号の追加・規定値の変更

記号の追加・規定値の変更では、通常unitと、対象記号を含む小さな接続例の両テーマ生成・検証を行う。整合性確認の省略条件は上記に従う。生成物用コマンドの同じ出力にある`qa/light.browser.png`と`qa/dark.browser.png`を目視し、PPTX出典の役割・寸法・色、ラベル、接続、編集可能な標準図形、画像の非埋め込みを確認する。同じ例をnativeテストで重ねて生成せず、記号情報と例だけの変更で全受け入れ検証を追加しない。

全記号一覧への登録漏れは通常unitの`test_real_world_topology_contracts`で確認する。`verified-symbols.json`の描画は、一覧自体を成果物として生成・更新する場合、既存記号の配置・ラベルや共通描画条件を変更した場合、および全受け入れ検証で行う。記号の追加登録だけを理由に接続例と一覧の両方を描画せず、未描画の一覧を目視確認済みとは扱わない。Web・DRなど既存構成も追加記号へ一括置換しない。

リソース記号は既存の共通unitで標準図形ID・寸法・色・接続先を確認する。接続例はDynamoDB Streamsが`examples/real-world/dynamodb-streams.json`、S3 Bucketが`examples/real-world/s3-bucket.json`。PPTXの出典・値は`native-catalog.json`の各記号を参照し、S3 BucketはGeneral purpose bucketとしてDirectory bucketやBucket with objectsと区別する。通常の12 ptラベルと既存の接続規則を使い、サービス名の厳密照合をリソース名へ拡張しない。輪郭は標準図形による近似として扱う。

### 手動経由点とテーマ固定の変更

manual-waypoints.jsonの経由点、または原本のadaptiveColorsを変更した場合は、通常unitと次の対象nativeを実行する。他の構成例の経由点だけを変更した場合は、その例だけを確認する。構成例そのものをブラウザ計測で生成・検証し、テーマ固定指定の有無でSVGの描画内容とPNGが変わらないことを確認する。同じ例を別途生成し直さず、保持したout/qaの両テーマ画像を目視する。

```sh
AWS_NATIVE_DRAWIO_RUNTIME=<runtime.json> AWS_DRAWIO_PROFILE=<dedicated-profile> python3 -B <skill-dir>/scripts/test_runner.py --group native --match ManualThemeNativeTests --keep-artifacts --output <new-check-dir>
```

OSやアプリのテーマ設定は変更しない。XMLの属性確認と書き出し検証は、異なるOSテーマでのエディター表示確認とは区別して報告する。

### 配置表・図形制限の変更

通常unitでは小さな独立構成を使い、未検証の標準図形の受付、直線の経由点、配置表の方向・レーン、接続点の一致、障害物の検出、既存出力の保護、ブラウザ・draw.ioなしでの原本生成を確認する。実用例の交差数は固定値の合格条件にしない。新しい判定器は作らず、端点・障害物は既存検査を再利用する。接続点の切り出しは、既存例とプロジェクトの各ビューの両テーマ原本・layout・警告が切り出し前後で一致することを一度確認する。

配置表の生成・描画に影響する実装や例を変更した場合は、上記の配置表コマンドでmulti-az-waypoints.jsonとmulti-az-waypoints.spec.pyを指定し、runtime・export付きで両テーマを生成・目視する。これに同じ例のrun.py再生成や全受け入れ検証を重ねない。初回確認が済むまでは、その環境での実描画は未確認として記録する。

経路の比較が必要な場合だけ、同じ配置表のPOS・W・Hからapply_specで入力を作り、接続からsource_side・target_side・waypointsを除いた自動経路と、waypoints.buildの指定経路を比較する。両方とも同じ文字幅条件を使う。report.jsonのrouting_qualityに交差・曲がり・長さを記録し、W_EDGE_CROSSINGSの有無だけに依存しない。比較値は描画の合否や性能保証ではない。

### 開発用の全受け入れ検証

```text
python3 -B <skill-dir>/scripts/acceptance.py --output <new-dir> --profile <dedicated-profile> --runtime <runtime.json>
```

大規模な生成・検証処理の変更で包括的な確認が必要な場合に、全テスト、examples/real-world、構成正本の全ビュー、配置検証用の入力群を直列に実行し、両テーマを目視する。密な入力の拒否と表示サイズ不足の検出も受け入れ条件に含める。実行環境が不足している場合は停止し、自動導入で補わない。acceptance-summary.jsonには完了済みの結果と、テスト・実利用例・プロジェクト・入力群ごとの時間を保存する。例外で中断した工程の時間と失敗理由も残す。

全テストを同じソース・環境で別途完了した場合、`--cases-only`で受け入れ事例だけを実行できる。この結果のscopeはcases-onlyであり、全テストの成功を含まない。配布判断には両方の結果を確認する。修正がない成功済み検証を理由なく繰り返さない。

実行時間の比較は、同じ実行環境・対象事例・順序で行う。テスト件数の増減、初回と再実行、タイムアウトを区別し、1回の測定だけで安定した短縮率とは説明しない。CIの未有効化の雛形は[ci-template.yml](ci-template.yml)を参照する。

## ZIPの同梱確認

ZIPの収集対象や文書だけを変更し、図の生成・生成物検証処理が不変なら、配布テストと新規ZIPの確認に絞る。配布テストは、同じソースで通常unitが全件合格済みなら重ねて実行しない。また、次の条件をすべて満たす文書・配布と無関係なテストの変更では、過去の配布テストの合格結果を再利用できる。

- 変更は文書の本文、配布と無関係なテストの内容、およびそれに伴う版番号・manifestに限る。動作コード、配布要件、収集対象・ファイル名は変えていない。変更したテストは、変更内容別の条件に従って別途確認する。
- 合格時のソースと比較して、配布処理・整合性検査・関連テストとその依存に変更がなく、実行環境も同じである。
- 対象の配布テストが省略・失敗なく完了した記録があり、対象コミット・検査範囲・結果を特定できる。

再利用時は、参照した合格記録と変更がないことの確認結果を記録する。どちらの省略条件にも該当しない場合は次を実行する。全受け入れ検証や再描画の合格を意味するものではない。

```sh
PYTHONPATH="<skill-dir>/scripts:<skill-dir>/tests" python3 -B -m unittest test_version.ReleaseTests test_bundle.BundleTests
```

テスト結果を再利用する場合も、変更後のソースから新規ZIPを生成し、同梱内容を確認する。

```sh
python3 -B "<skill-dir>/scripts/package_release.py" --output "<new-package-dir>"
```

`package_release.py`はLICENSE・README.md・THIRD_PARTY_NOTICES.mdを必須の収集対象とし、同梱ファイルのハッシュをmanifestへ記録する。欠落・symlinkは出力前に拒否する。既存の配布テストで文書の内容一致、欠落・symlink拒否、再現可能性、入力非変更を確認する。生成時に`check_bundle.audit()`も呼ばれるため、成功した同じZIPを単独の整合性検査でもう一度検査しない。ZIPに必要な文書が入ったことと、旧成果物に変更がないことを記録する。

旧版ZIPの読み取り検査に新しい文書要件を遡及適用しない。機械検査は権利の有無を判定しないため、公開前には[第三者権利の説明](../THIRD_PARTY_NOTICES.md)を確認する。

## 公開候補の確認

公開候補を作成・更新したときだけ、ZIPと展開ソースのファイル集合・内容が対象コミットと一致することを確認する。ZIP内部の整合性は生成時の検査結果を再利用する。ファイル名・本文・ZIPメタデータに個人名、個人ID、個人メール、ホームパス、認証情報がなく、Git履歴や作業ログが混入していないことを確認する。第三者の権利表示・出典は削らず、GitHubの所有者IDは許容する。文書だけの変更では再描画や全unitを追加しない。

新規リポジトリの作成が承認され、履歴を引き継がない公開用作業フォルダを用意した後は、コミット時に作者・コミッターを次のように一時指定する。環境変数はこのコマンドだけに適用し、Git設定へ保存しない。`.invalid`のアドレスは連絡先やGitHubアカウントとの紐付けに使わないプロジェクト用の表記である。

```sh
GIT_AUTHOR_NAME="aws-architecture-drawio contributors" \
GIT_AUTHOR_EMAIL="contributors@aws-architecture-drawio.invalid" \
GIT_COMMITTER_NAME="aws-architecture-drawio contributors" \
GIT_COMMITTER_EMAIL="contributors@aws-architecture-drawio.invalid" \
git -C "<public-repo>" commit -m "Initial public source"
```

既存の非公開リポジトリへの通常の保存とは区別する。push前に以下で送信する履歴の名義・本文を確認する。署名を付ける場合は署名情報も確認し、個人情報が残る場合は公開せず名義を調整する。未作成のコミットまで確認済みとは扱わない。

```sh
git -C "<public-repo>" log --all --format=fuller --show-signature
```
