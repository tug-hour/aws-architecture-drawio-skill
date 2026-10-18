# JSON補助ツールの入力仕様

直接作図ではこの形式は不要である。以下はrun.py・waypoints.pyなどを使う場合だけ適用する。

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
