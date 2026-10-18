# 配布・導入・更新の手順

## 配布物

配布単位はaws-architecture-drawio-<version>.zipと同名の.zip.sha256。ZIPの直下にaws-architecture-drawio/SKILL.mdがあり、LICENSE・README.md・THIRD_PARTY_NOTICES.md、標準図形カタログ、参照仕様、プログラム、テスト、実利用の構成JSONを含む。アイコン画像、フォント、draw.io本体、Node.js、ブラウザは含まない。検証図・レポートは別の資料として渡す。

checksumは取得元の信頼を確認してから使う。SHA-256と内部manifestは変更・混入を検出するが、署名付き配布物の認証ではない。

## 配布物の生成

版番号の定義元は[version.json](version.json)のみ。安定版のmajor.minor.patch形式で管理する。入力のschema_version、対応draw.io版、過去の検証履歴の版は別の情報として維持する。verification-summary.jsonは記載された版の過去の検証記録であり、現行版の合格証明へ書き換えない。

生成と確認の条件・コマンドは[ZIPの同梱確認](rendering.md#zipの同梱確認)を参照する。

設置先のSKILL.md・LICENSE・README.md・THIRD_PARTY_NOTICES.mdと、scripts・tests・references・examplesからZIP、外部checksum、release-manifest.json、package-result.jsonを新規出力先へ生成する。追加依存、ダウンロード、設定変更、自動更新は行わない。ソースと既存の出力先への書き込みは拒否する。キャッシュは含めず、symlinkは拒否する。

配布名とmanifestのversionは定義元から生成する。ソースにある旧release-manifest.jsonは入力に使わず、ZIP内では再生成したものを使用する。manifestはversion.jsonを含む全配布ファイルのSHA-256を保持し、自身だけを対象外にする。ソース側のmanifestも更新する場合は、ソース変更を終えて生成・検査したrelease-manifest.jsonを、承認済みの更新範囲でreferencesへ反映する。

出力のcandidate_versionとプロジェクト・受け入れ検証のversionは同じ定義元を読む。再描画検証は生成時の版が一致する場合だけ実行し、ビューアーもプロジェクトの版が一致する場合だけ生成する。版の欠落・不正値は停止条件で、推測や既定値では補わない。

## 一般公開用の候補と公開判断

カタログを含む現行の配布範囲を公開候補とする。権利の適用範囲と公開判断は[第三者権利の説明](../THIRD_PARTY_NOTICES.md)を参照する。

既存の開発リポジトリは履歴を含めて非公開で保管する。公開候補には、検査済みZIPとchecksum、および同じZIPから展開したソースだけを専用フォルダへ置く。package-result.json、検証ログ、runtime、作業フォルダ、既存の.gitは含めない。新しい公開用リポジトリへ履歴を引き継がず、候補のファイルから開始する。新規リポジトリの作成と一般公開は、対象版・保存先・公開範囲・権利の未確定事項について承認を得てから実施する。

公開前の確認条件と、端末設定を変更しないコミットの名義指定は[公開候補の確認](rendering.md#公開候補の確認)を参照する。

## 検証済み一覧

記号のsupport_status、グループの種類、対応draw.io版の定義元はnative-catalog.jsonである。verified-assets.jsonのassets・group_types・drawio_versionは、その定義から生成する。platformとscopeは検証範囲の説明として保持し、生成処理で対応範囲を広げない。

```text
python3 -B <skill-dir>/scripts/verified_assets.py --output <new-index.json>
```

生成先は新規ファイルに限る。内容を確認し、承認済みのスキル更新としてreferences/verified-assets.jsonへ反映する。引数なしの実行は、設置先を変更せず一覧の整合性を確認する。配布生成とZIP検査でも、記号・グループ・draw.io版の不一致や一覧内の重複を拒否する。ハッシュが一致するだけでは、この検査を省略しない。

## 導入前の安全確認

既存のPython、draw.io、ブラウザ、フォントと対応バージョンを確認する。新規導入や更新が必要な場合は、配布元、依存関係、インストール処理、権限、脆弱性と修正状況、保存先、設定への影響、自動更新を確認し、承認後に導入する。スキル自身は導入を実行しない。

アーカイブを信頼できる元資料と照合して、次の読み取り専用検査を行う。

```text
python3 <skill-dir>/scripts/check_bundle.py --archive <aws-architecture-drawio-<version>.zip> --checksum <aws-architecture-drawio-<version>.zip.sha256>
```

この検査はファイル集合、内部manifestのハッシュ、CRC、危険なパスやsymlinkに加え、version.jsonの形式とmanifestの版一致を確認する。カタログなどへの配布版の重複定義も拒否する。展開・インストール・設定変更は行わない。旧配布物で版定義やmanifestがない場合は既定で拒否する。過去の配布物を調査する場合だけ--allow-legacyを明示でき、その場合は未検証の版整合性を警告する。版定義が存在する場合の不正値や不一致は、この指定でも拒否する。

## 新規導入

1. アーカイブを新規の専用ステージング領域へ展開する。ホーム全体を共有せず、不要な秘密情報を渡さない。
2. ソース・manifest・対応範囲を確認する。ブラウザ計測や厳密検証を使う場合だけ、既存runtime JSONと専用draw.ioプロファイルを参照する。
3. [描画と確認](rendering.md)に従い、利用する機能を導入先で確認する。全開発テストを導入の必須条件にしない。
4. 個人スキル領域などへ設置する場合は、配置先・書き込み・影響をまとめてユーザー承認を得る。
5. 導入した版、checksum、検証環境、結果、設置先を記録する。新しいタスクでスキルの発見・呼び出しを確認する。発見に必要なアプリ操作や設定変更も、実行前に影響を確認する。

## 更新と旧版への復帰

既存のスキル・手修正した図・構成JSONを保護する。旧フォルダへ上書きせず、新版を別の専用領域へ展開して検査する。利用中の版にローカル変更がある場合は差分を確認し、内容を保存してから更新する。

構成正本、必須経路、図の網羅、表示サイズを検査する。schema_version=1.0は維持するが、labelに混在した用途説明はdescriptionへ移行する。名称と改行の検査はdraftでも適用する。複数図の経路網羅を機械検査する場合だけプロジェクト形式を使う。旧版と手編集の成果物を保管し、新版では構成JSONから再生成する。

更新先への切替・置換には事前承認が必要。検証後の切替で、旧版と元の入力・図を残す。問題があれば、確認済みの旧版フォルダと対応する入力を選び直す。古い生成物を新しい検証結果で合格したものとして扱わない。旧版の削除・整理は別の明示的な許可を得る。

自動更新はスキルに実装しない。draw.io実行は--disable-updateを指定し、常用プロファイルを使わない。依存を更新する場合や対応バージョンを追加する場合は、その環境で再検証する。

## 開発用の自動検証とCI

開発・配布時の検証条件とコマンドは[スキル開発用の検証](rendering.md#スキル開発用の検証)を参照する。個々の図に適用する手順は[生成物用の検証](rendering.md#スキルの生成物用の検証)を参照する。

CIは、承認済みのMac arm64・検証済みdraw.io・runtime・フォントを持つ専用runnerを使う。references/ci-template.ymlは未有効化の雛形で、リポジトリの設定を変更するまで実行されない。外部CIへのrunner登録、Secrets・Variables、workflow有効化では、対象と権限、保存領域、機密情報、通知・公開の影響を確認し、承認後に設定する。

Mac固有の描画を含むため、利用者が承認したホスト環境を使う。Linuxコンテナだけで同等の描画を検証したとは説明しない。CIで指定するruntimeには、runner上の承認済みローカルファイルを使い、フォントをアーカイブへ同梱しない。

配布物からの実行・更新・復帰は[release-rehearsal.md](release-rehearsal.md)を参照する。個人スキル設置とアプリの発見確認は、この検証とは別に承認後に実施する。
