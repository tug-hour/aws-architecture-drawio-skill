# スキル開発・配布の検証

スキル自体を変更・配布する場合に参照する。利用者の通常作図は[生成・確認](rendering.md)に従う。

## スキル開発用の検証

スキルの実装・構成例の変更による回帰を調べる。テスト用入力や意図的に不正にした成果物を使い、検出処理も確認する。利用者の個々の図を検証した結果とは区別する。

変更内容と影響範囲に応じて次の検証を選ぶ。配布・導入だけを理由に全受け入れ検証を追加しない。実行条件とコマンドは本書を定義元とし、同じ観点を確認済みの検査は重ねて実行しない。

| 変更内容 | 開発用の検証範囲 |
| --- | --- |
| 文書・版管理情報のみ | 内容、参照リンク、SKILL.mdの基本形式、版と配布manifestの整合性。描画・回帰テストは追加しない |
| 構成例のみ | その例に関係するunitと、変更した例の生成・目視。drawio/1は通常生成で例に指定されたテーマ、旧JSON生成・照合ツール用の例は任意の厳密検証で両テーマ、配置表の例は配置表コマンドを使う |
| 生成・検証コード、処理が参照する規則やカタログ | unit。図形一覧の定義・生成・照合に影響する場合は一覧の整合性も確認する。実描画への影響がある場合は該当するnativeを実行する |
| テストのみ | 変更したテストを`--match`で実行する。共通fixtureやテスト選択・実行処理を変更した場合は、その影響を受ける範囲も含める |
| ZIPの収集対象・同梱文書だけの変更 | 下記の配布用検査。生成・検証処理が不変なら描画は追加しない |
| 生成・検証処理を広く変更し、対象を絞った確認では足りない場合 | 下記の全受け入れ検証と、生成した両テーマの目視 |

### JSONからの通常生成の変更

`test_drawing`は小さな独立構成で、親子座標・文字・未登録の標準図形・接続点・経由点、局所更新時の無関係なセルの保持、入力と既存出力の保護を確認する。通常unitに含まれるため、全件合格後に重ねて実行しない。開発中に対象だけを実行する場合は次を使う。

```sh
python3 -B "<skill-dir>/scripts/test_runner.py" --group unit \
  --match test_drawing --output "<new-test-output-dir>"
```

共通のXML生成処理を変更した場合は通常unitで旧形式の回帰も確認する。実際の図形・文字・経路の出力に影響する場合だけ、変更した入力の原本を表示する。構成例の導入時は、既存図との位置・スタイル・文字・接続の比較と、その同じ出力の目視を行う。大きな構成例を通常unitへ追加せず、通常生成と旧形式の厳密検証で同じ図を重ねて生成しない。機械的な生成時間と、編集・表示・目視を含む作業時間は区別して記録する。

部品操作の変更では同じ`test_drawing`で作成・複製・親変更・内部経由点の一度だけの移動・外部経由点の保持・スタイル衝突・入力非変更を確認する。通常生成と互換APIの分離は、CLIが旧配置モジュールを読み込まないことと既存API・エラーの互換性を確認する。通常作図の追加検証にはしない。

### 経路補助の変更

`drawio_routes.py`の読取・診断と明示接続点は、小さな独立構成を使う`test_drawio_routes`・`test_waypoints`で確認する。入れ子座標・全文字領域・過小な文字高さ・未解析部分・線分共有・配置入替による交差低減、ロックされた図形の衝突と背景・装飾の除外、簡潔なCLI出力での指摘保持と入力非変更を対象にする。通常unitに含まれるため、unit完了後に同じテストを単独で再実行しない。開発中に対象だけを実行する場合は既存test_runnerの`--match test_drawio_routes`または`--match test_waypoints`を使う。

読み取り専用の診断だけの変更では再描画しない。共通経路処理を変更する場合は通常unitで従来の生成・失敗条件を確認し、描画される経路が変わる場合だけ、その例の指定テーマを表示する。大きな既存図は調整効果の任意比較に使い、通常unitへ取り込まない。改善時間を比較する場合は同じ構成・環境で作図と描画に要した時間、描画回数を記録し、解析時間だけを作図時間の短縮として報告しない。

### 導入・更新時の確認

利用する機能と変更の影響範囲だけを確認する。drawio/1を使う場合は通常生成、直接作図の場合は直接編集した確認用の図を一度表示すればよく、ブラウザ計測や全開発テストは不要である。旧形式の厳密な照合が必要な場合だけrun.py・project.pyを使う。変更していない既存図を、スキルの更新だけを理由に再生成しない。

描画結果を再利用する場合は、対象入力・配置表・描画に関係するコードと規則・実行環境が確認時と同じで、生成と目視が完了した記録を参照する。文書やテストだけの変更なら再描画を追加しない。記録には対象版・コミットと今回の差分を示し、過去の結果を現行版で再実行したとは扱わない。配布物の確認は[ZIPの同梱確認](#zipの同梱確認)に従う。

### 構成例・配置・警告の変更

プロジェクトの一部ビューの配置だけを変更した場合は、`project.project_views()`で正本全体の参照・必須経路・ビュー網羅を確認し、変更したビューの`architecture`を新規JSONへ保存する。そのJSONを[互換用の単独図コマンド](legacy-rendering.md#任意の厳密な生成物検証)で生成・検証し、`quality.operational_quality()`で元ビューの`display`に対する表示品質も確認する。対象ビューID、正本のハッシュ、保存先、結果を記録し、全ビューの描画検証とは区別する。枠同士や見出しとの重なりも両テーマで目視し、経路警告がないことだけで配置を合格としない。モデルや共通設定も変更した場合は、その影響先を対象に含める。

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

関連nativeテスト内でrun.pyによる両テーマの生成・生成物検証が完了し、変更した条件を確認できる場合は、別の代表構成を重ねて生成しない。開発用のテスト結果と、その実行内の生成物用レポートを区別して記録する。目視が必要なら同じ実行の生成物を保持して確認する。追加実行は、選んだテストで確認できない観点がある場合に限る。利用者が別途作成する図には、[通常作図の確認](rendering.md#スキルの生成物用の検証)を適用する。

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

nativeは承認済みの実描画環境で実行する。環境の選択は[既存環境の手順](legacy-rendering.md#既存環境を使う場合)に従う。

```text
AWS_NATIVE_DRAWIO_RUNTIME=<runtime.json> AWS_DRAWIO_PROFILE=<dedicated-profile> PYTHONDONTWRITEBYTECODE=1 python3 -B <skill-dir>/scripts/test_runner.py --group native --output <new-native-dir>
```

`--group all`は両群を実行する。unitとnativeの全件を同じソース・環境で完了した場合は、allを重ねて実行しない。`--match <test-idの一部>`は対象を絞る。実描画が必要なのに環境がない場合はunavailableで終了し、skipを成功に数えない。従来のunittest discoverも利用できるが、環境変数がない場合は実描画テストをskipする。

目視確認や失敗調査に生成物を使う場合は、対応テストを選んで`--keep-artifacts`を付ける。保持対応は各テストの`supports_artifacts=True`で宣言する。影響する対象を`--match`で選ぶ。この保持処理自体を変更する場合は、unitと対応テスト一件を実行し、終了後に保存先と生成物を確認する。

```text
AWS_NATIVE_DRAWIO_RUNTIME=<runtime.json> AWS_DRAWIO_PROFILE=<dedicated-profile> PYTHONDONTWRITEBYTECODE=1 python3 -B <skill-dir>/scripts/test_runner.py --group native --match AdvisoryNativeTests --keep-artifacts --output <new-native-dir>
```

利用者が別途指定した矢じりの種類・サイズの変更を実装する場合だけ、unitで旧設定との差が矢じり設定だけであることを確認し、次の関連nativeテストを実行する。片方向・双方向・無矢印、水平・垂直の終端とアイコンへの接続を同じ図で確認する。保存した両テーマを目視し、線幅・色・方向・経路と矢じり周辺の余白を確認する。

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

状態の切替、警告・要素ID、文字列の安全な表示を確認する。失敗・未確認の各ビューから合格・要確認の各ビューへ切り替え、[結果表示の仕様](legacy-rendering.md#任意の厳密な生成物検証)にある図専用操作と案内の非表示・復元、画像とリンクの参照先、復元後の拡大操作を確認する。`browser-check.json`に結果と時間を保存し、同じ出力先の`light.viewer.png`・`dark.viewer.png`・`failed.viewer.png`・`unknown.viewer.png`を目視する。この表示確認は新たな図の生成物検証ではない。判定・生成処理にも変更が及ぶ場合は、上記の変更内容別の検証条件を適用する。

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

配置表の生成・描画に影響する実装や例を変更した場合は、[配置表コマンド](legacy-rendering.md#配置表を使う場合)でmulti-az-waypoints.jsonとmulti-az-waypoints.spec.pyを指定し、runtime・export付きで両テーマを生成・目視する。これに同じ例のrun.py再生成や全受け入れ検証を重ねない。初回確認が済むまでは、その環境での実描画は未確認として記録する。

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
