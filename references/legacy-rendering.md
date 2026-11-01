# 互換用の描画・実行環境

旧`schema_version: "1.0"`の処理を使う場合だけ参照する。通常作図は[生成・確認](rendering.md)に従う。

## 配置表を使う場合

大きな図の配置・配線を反復調整する場合だけ使う。基本は既存Pythonの標準ライブラリで原本を生成する。入力と配置表の形式は[互換用の配置と経路](legacy-layout.md)を参照する。

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

旧`schema_version: "1.0"`入力で原本と入力の一致や再描画の再現性を厳密に確認したい場合だけ、既存のrun.pyを使う。複数図の網羅を機械検査したい場合はproject.pyを使う。`drawio/1`の通常生成には適用せず、以下を通常作図の必須手順にしない。

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

