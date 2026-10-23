# JSONの入力仕様

## 通常作図のdrawio/1形式

`format: "drawio/1"`は、構成・配置・配線の採用値を保存する形式である。JSONを変更して同じ生成処理を呼ぶと、編集可能なdraw.ioを作る。配置や接続点の自動再計算、カタログによる図形制限、ノード数の独自上限はない。生成コマンドと確認範囲は[rendering.md](rendering.md#jsonを更新元にする場合)を参照する。

| フィールド | 内容 |
| --- | --- |
| `page` | 任意の`id`・`name`とdraw.ioモデル属性の`model`。既定は白背景、ページ表示なし。`adaptiveColors`は`none`で固定する |
| `styles` | 共通スタイル名をキー、draw.ioのスタイル属性を値とする辞書。`{"group": null}`や`{"text": null}`は値なしのスタイル名、数値・文字列は属性値となる |
| `elements` | 安定した要素IDをキーとする辞書。`0`・`1`はdraw.io内部用。記載順は描画順になるため、局所更新で並べ替えない |
| `parent` | 親要素ID。省略時は最上位の`1`。枠、グループ、図形を親にできる |
| `bounds` | 図形・文字の`[x, y, width, height]`。単位はpx、位置は親の左上からの相対座標。1pt＝4/3px |
| `style`・`overrides` | 共通スタイル名と、その要素だけの上書き属性。`shape`には使用する標準図形IDを指定する。局所修正では共通スタイルの変更が他要素へ及ぼす影響に注意する |
| `value`・`connectable` | 文字列と接続可否。省略時は空文字と`true`。文字も独立要素として位置・寸法を編集できる |
| `source`・`target` | 接続元・先の要素ID。この2項目を持つ要素は線となり、`bounds`を持たない。枠を接続先にすることもできる |
| `source_port`・`target_port` | 図形内の相対位置`[x, y]`。左中央は`[0, 0.5]`、右中央は`[1, 0.5]`。指定時はスタイルの`exitX/Y/Perimeter`・`entryX/Y/Perimeter`と重複させない |
| `waypoints` | 線の親からの相対px座標を、通過順に並べた`[[x, y], ...]`。省略時は空。細かな配線を保持する場合は接続点と併せて指定し、自動経路のスタイルを使わない |

JSONの重複キー、不明参照、親子循環、非有限座標など、図を生成できない入力はエラーになる。交差や重なり、未検証の図形を理由に生成を止めない。PPTXの色・寸法などを自動補正する処理ではないため、[適用値](native-rules.md)をスタイルへ指定する。

### 構成例の再利用と更新

[servicehub.json](../examples/servicehub.json)はv10相当の構成例で、標準AWS図形・枠・文字・78本の接続を保持する。新規作図では必要な`styles`と`elements`を新しいJSONへコピーできる。構成・所属・接続関係が一致する部分は、枠・アイコン・文字と内部配線をまとめて取り出し、配置・接続点・経由点も再利用する。`node.kms`のような透明グループはアイコン・名称・役割の子要素と一緒に取り出す。複製時はコピー先と衝突しないIDへ対応付け、`parent`・`source`・`target`とスタイルの参照先を揃える。構成例全体や不要なサービス・接続は引き継がない。新しい配置に合う内部配線は保持し、外部への接続や周辺と干渉する箇所を調整する。線の親や座標系を変える場合は、経由点もその親からの相対座標へ合わせる。

既存配置の更新では、`node.kms.bounds[0]`を変更するとアイコン・名称・役割が一緒に移動し、接続先IDの`kms`は維持される。線の端点は移動先へ追従するが、途中の経由点は自動で移動しない。接続する線と周辺を併せて調整する。

KMSとCognitoを結ぶ`key`の接続点は`source_port`・`target_port`で変更できる。無関係な要素・配線は触らず、図形追加時も新しいIDと必要な接続だけを追加する。アイコン本体だけを親グループの中で動かすと、兄弟要素のラベルは動かない。

1ファイルは1ページ・1テーマを表す。テーマの自動変換やGUI変更の自動取り込みは行わない。複数テーマが必要なら、それぞれの背景・共通スタイルを設定したJSONを保存する。通常作図に両テーマを強制しない。

## 互換用のschema_version 1.0形式

以下は既存の`run.py`・`waypoints.py`・`project.py`を使う場合だけ適用する。`build_drawio.py`は`format`のある入力を通常生成へ、従来の`schema_version`入力を既存処理へ振り分ける。以下の上限や固定ラベル、必須の描画環境を`drawio/1`へ適用しない。旧入力を自動移行せず、既存の結果を維持したい場合は元の形式と手順を使う。

schema_version=1.0。nodesとedgesは必須。modeはproduction（既定）／draft。run.pyのproductionはdraw.io 32.4.1とブラウザ計測が必要。図形の検証履歴による使用制限は両モードとも設けない。未確認の図形にはW_UNVERIFIED_ASSETを出す。未知のIDは両モードで拒否する。

themeはlight／dark／both、既定light。profileはstandardのみ。directionはleft-to-right／top-to-bottom。canvasはauto、またはfixedとwidth_pt・height_pt。layoutはauto、またはmanualとpositions。座標はpt。manualは全ノードのnode_id・x_pt・y_ptを指定する。自動配置は循環する包含範囲の制約を拒否する。

nodesはid、asset_id、任意label・description・label_kind・group_id。asset_idはaws4.lambdaなどの標準ID、または既存の別名。サービス名は最大2行。AWS／Amazonを単独行にしない。汎用記号user・usersはgeneralとして、36 pt、ライト#242F3E・ダーク#FFFFFFを使う。

groupsはid・type・role、任意label。containmentはparent_id、overlayは2つ以上の異なるノードIDをmembersへ指定する。overlayはparent_idを持たず、ノードのgroup_idから参照しない。AWS Cloudのみcloud_icon=logo／cloudを指定できる。空の包含グループは拒否する。

edgesはid・source・target、任意direction=forward／both／none、waypoints。自分自身への接続は未対応。labelは単一行・最大80文字。表示位置を自動で選び、空白がなければE_CONNECTION_LABEL_SPACEで拒否する。source_side／target_sideはleft／right／top／bottomを指定できる。bottomもラベルとの衝突検査を受ける。waypointsはx_pt・y_ptを持つ非空配列で、manual配置とfixedキャンバスの場合だけ指定できる。配置・接続点・障害物・警告の詳細は[配置と経路](layout-and-routing.md)を参照する。

用語集glossaryはasset_id・full_name・short_name。各項目は単一行、略称の重複は拒否する。図の上に「full_name (short_name)」を描画し、ブラウザ検査に含める。本文における正式名称の初出順はこのプログラムの検査対象外。

未知・重複キー、非有限数、ID重複、不明参照、親子循環、空ラベル、制御文字、入力型の不一致を拒否する。最大200ノード・500接続・60グループ。ただし実描画の受け入れ検証は27ノードまでで、上限までの品質・性能を保証しない。経路グリッドが上限を超える場合は分割を要求する。

callouts、regions、annotations、standard以外のprofileは未対応として拒否する。指示された要素を黙って落とさない。自動縮小・自動省略は行わない。

一括実行の終了コードは0＝生成と検査成功、2＝入力・規定・整合性違反、3＝実行環境不足または検証実行の失敗、4＝生成処理の失敗。result.jsonを成功・失敗の両方で保存する。既存出力先を指定した場合は変更せず、標準出力にエラーを返す。

成功時はarchitecture.json、layout.json、measurements.json、各テーマのdrawio・SVG・PNG、validation.json、artifact-manifest.json、qa/browser-validation.json、qa/*.browser.png、result.jsonを保存する。production_eligible=trueはこの限定した対応範囲の検査成功を意味し、AWS構成の妥当性やPPTXとの完全一致を意味しない。

包含グループの内側に、親子関係を持たないノードの中心が入る場合はE_GROUP_VISUAL_MEMBERSHIP。図が誤った所属を示す配置を拒否する。横断グループは既存の所属を変えないため、この包含検査の対象外。

任意のavailability契約とedges.purposeは[冗長化・切替](availability.md)を参照する。名称・説明分離を満たす既存入力は受け付けるが、以前の経由点が新しい24ptの端点直線条件を満たさない場合は明示的に拒否する。配置と経路は再生成する。


layout.frame_padding_ptは12〜72pt。既定12pt。主図とWeb詳細図は24ptで、包含枠の余白を広げる。見出しの障害物範囲には実測した文字と記号だけを使い、空白部分へ線が入ることを禁止しない。枠を横断する線と、枠に近接して並走する線を区別する。後者は18ptの離隔を優先し、48ptを超えて近接並走する場合は警告する。

一般記号のlogical_idは、同一主体を通常/切替後の位置へ再掲するための明示宣言。正規の要素IDとは別で、同一logical_idは同じ一般記号IDを使う。図中のラベルと凡例にも同一主体・再掲の意味を明記する。異なるサービスへlogical_idを付けて接続を補うことは禁止する。Readerやサービスの接続をこの機能で省略しない。

productionで接続がある構成に孤立ノードが残るとE_ORPHAN_NODE。図形一覧のように接続が全くない入力は作図の形状検査のみであり、アーキテクチャーの完全性を保証しない。孤立した障害物記号を使う経由点デモはdraftに変更した。

semanticsによる経路契約と、構成正本からの図の生成は[projects-and-flows.md](projects-and-flows.md)を参照する。schema_version=1.0を維持するが、0.6.1ではサービス名の検査を強化する。旧labelに用途説明が混在する入力はdescriptionへ移行し、重要経路の宣言がない単独図を正式運用向けの意味検査済みプロジェクトと扱わない。

サービス名とdescription、正式名凡例、互換性は[名称とPPTX適合範囲](service-labels-and-conformance.md)を参照する。draftでもサービス名の検証を省略しない。名称方針が未登録のサービスも受け付け、名前と記号の対応は人が確認する。リソース・汎用ラベルにはサービス名の2行規定を転用しない。汎用名は用途に応じて変更できる。リソース記号との名称一致は人が確認する。
