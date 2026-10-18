# サービス名とPPTX適合範囲

本書はJSON補助ツールの名称処理と、標準図形によるPPTX規則の適用範囲を説明する。通常の直接作図に名称辞書への登録を要求しない。AWSによる承認、元のSVGの同一性、PPTX完全準拠を表さない。成功時もaws_conformance=partialとする。

## サービス名

JSON補助ツールでは、service-names.jsonに登録済みのサービスのlabelをallowed_namesと照合する。未登録サービスも受け付け、名称は使う図で確認する。入力された改行をスペースで連結した名前が、該当記号の許可名と一致しなければ拒否する。別サービス名、単語途中の改行、ブランドだけの行、3行以上、改行前後の余分な空白は受け付けない。AWS/Amazonを最初のサービス語と同じ行に置く。サービス名の大文字小文字も出典に合わせる。

用途説明はdescriptionへ分離し、単一行・最大120文字とする。名前と説明は同じ12 ptの文字で描画し、サービス名の2行制約は説明には転用しない。名前・説明・見出し・接続の略称から、必要な正式名を図の先頭へ自動生成する。該当サービスの正式名をlabelに表示し、そのノードのdescription内だけで略称を使う場合は、自動凡例を省く。正式名の改行は単語境界として照合する。他のノード・見出し・接続・注記（short_nameの見出しとfull_nameの本文）にも略称があれば、読順を保証できないため凡例を残す。入力で明示された定義と注記は削除しない。各ビューで必要な定義を独立に生成し、前の図を見ないと分からない短縮表記にしない。入力glossaryのdefinitionは出典付きの正式名・短縮形と照合する。kind=noteは配置や構成の補足であり、正式名の定義に代用できない。同じ略称の重複は拒否する。

S3、SQS、SNS、ECS、EC2、RDSの展開名は公式AWSドキュメントに基づく。AWS WAFはPPTXと公式文書で使われる正式な名称を維持し、機械的に別の製品名へ展開しない。略称判定は登録された名前に限る。任意の専門用語の意味や、未登録サービスの別名を推測しない。draftも登録済みの名称には同じ検査を使う。名称方針の追加を図形使用の前提にはしない。

## AZ所属の表示

AZ枠の名前と包含関係から所属が一意に分かる場合は、ノードの表示ラベル（label・description）に同じAZ名を繰り返さない。例えば「ECS API・AZ-A」は「ECS API」、「ECSワーカー・AZ-C」は「ECSワーカー」とする。所属はgroup_idとグループのparent_idに保持し、AZ枠の名前は残す。枠を省略した図や所属が曖昧な図では、必要なAZ名をdescriptionに明記する。複数AZを利用するALBの説明、Writer/Readerや昇格条件などの役割・条件は省略しない。これは作図時の方針であり、入力文字列からAZ名を自動削除する処理や、旧入力を拒否する検査は追加しない。

確認補助として、group_idからparent_idをたどり、AZ枠が一つで、その見出しにAZ-Aのような「AZ-＋半角英数字」が一種類だけ明示される場合に、label・description中のAZ名への言及を照合する。同じAZ名ならW_AZ_LABEL_REDUNDANT、異なるAZ名ならW_AZ_LABEL_MISMATCHを報告する。「東京 AZ-A」「AZ-A（主系）」「東京 AZ-A / 主系」「AZ-A, primary」も対象にする。警告にはノードと枠のID、両方のAZ名、対象フィールドを含める。同じノードについて両フィールドに言及があっても、警告は一件にまとめる。

複数のAZ名、AZ-A/C・AZ-A,Cのような省略列挙、複数のAZ祖先枠、明示的なAZ名のない独自の見出し、AZ枠のない図は自動照合の対象外とする。スラッシュ・カンマ・読点の後ろが同じ形式の省略名なら列挙と扱う。形式は英字数と数字列の位置で比較し、数字列の桁数は問わない（AZ-A/C、AZ-1/22、AZ-1a/2bなど）。それ以外の補足付き表記は、一種類のAZ名が明示される場合に確認候補とする。意味を推測して省略名を展開したり、別の枠名やAWSのAZ名へ対応付けたりしない。警告は重複や所属の誤りを確定せず、終了コードや合否を変更しない。接続先・切替条件への言及も候補になるため、役割・条件を消さずに人が確認する。警告がないことも、この作図方針への適合を証明しない。

## 互換性

schema_version=1.0を維持するが、旧版でlabelに用途・Writer/Readerなどを混在させた入力は、新版で受け付けない。正しいサービス名だけをlabelに残し、用途・役割をdescriptionへ移す。Auroraの役割検査は名前とdescriptionの両方を参照する。単語途中で改行された旧名や、記号と異なる旧名を自動補正しない。

E_SERVICE_NAMEとE_SERVICE_LABELには、details.migrationとして対象フィールド、入力名、アイコンの許可名、既存description、移行手順を添える。許可名と用途が明示的な区切りで分かれている場合はsuggested_fieldsに修正候補を示す。候補は人が確認して新しい入力へ適用するもので、プログラムは入力を変更しない。既存のエラーコードと拒否条件も維持する。

例えばlabelが「Amazon Aurora Writer」、descriptionが「昇格後もReaderを保持」の場合、候補はlabelが「Amazon Aurora」、descriptionが「Writer / 昇格後もReaderを保持」となる。既存descriptionを上書きで失わず、役割・条件を残す。単語途中の改行や別サービス名は意図を推測して直さず、許可名と入力を確認する。descriptionが120文字を超える候補は提示せず、内容を切り捨てない。旧入力を保存し、移行後の入力は別名で作る。

正式名凡例は自動キャンバスでは上部に追加し、全ノード・枠・接続・接続ラベルを同じ量だけ下へ移す。アイコン・文字は縮小しない。固定キャンバスでは上部の空き領域を明示的に確保し、足りない場合はE_GLOSSARY_OVERFLOWで停止する。用語集追加後の表示サイズも品質検査に含める。

## 適合範囲

| 分類 | 範囲 |
| --- | --- |
| 数値・配色対応 | 検証済み記号の外形、カテゴリ色、グループ30 pt、枠1.25 pt・塗りなし、背景色、矢印色、12 pt文字、入れ子余白 |
| 近似 | draw.io AWS4の輪郭・余白、Openの矢じり。破線比率もOOXMLをdraw.ioへ変換した結果であり、元PPTXの画素一致ではない |
| 拡張 | 日本語Arial Unicode MS、名前と用途説明の分離、ブラウザ計測、配置・経路検査 |
| 未対応 | コールアウト、Arch_32を使うカスタムサービスグループ、縦長文書、Training and Certification、リージョンからのロゴ自動選択、全1050記号の名称・形状検証、他OS |

16種類のグループ記号を両テーマで比較し、VPCを含む対応と輪郭の差を記録している。この比較は輪郭の完全一致を示すものではない。

JSON補助ツールでは未対応のprofile、callouts、region_id、未知のgroup.typeを拒否する。通常の直接作図の制約ではない。AWS Cloudのロゴ例外は利用者がcloud_icon=cloudを明示する。厳密なPPTX完全準拠が必要な用途では本方式の制約を説明し、完全準拠として納品しない。輪郭の一致には公式SVG方式など別の検証が必要であり、画像を使わない方式へ黙って置き換えない。

AWS Cloudのテーマ別配色と、図形の抜き部分に使う下地は[native-rules.md](native-rules.md)に定義する。リソース記号と任意ラベルの名前の一致は機械検査の対象外で、人が確認する。

## 出典

- 添付AWS Architecture Icons Release 23-2026.01.30：L15–17/D13–15、L25–27/D23–25。各記号のスライド参照はservice-names.jsonに保存する。
- [Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html)、[Amazon SQS](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html)、[Amazon SNS](https://docs.aws.amazon.com/sns/latest/dg/welcome.html)
- [Amazon ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html)、[Amazon EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/concepts.html)、[Amazon RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html)、[AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/waf-chapter.html)
