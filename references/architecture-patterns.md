# 実利用を想定したAWS構成

この構成は作図スキルの受け入れ検証用の設計例であり、AWSリソースを作成・変更するものではない。アプリケーションの配備、実トラフィック試験、障害試験、IAMポリシーの実環境検証は行っていない。

## 前提と構成

CloudFront＋S3でSPAを配信し、Web APIと非同期ワーカーはAmazon ECS on AWS Fargateで実行する。IoT Coreでデバイスのデータを収集し、最新状態をブラウザへストリーミングする。リージョン内はMulti-AZ、リージョン間は東京を主系・大阪を待機系とするwarm standbyを選ぶ。これは今回の検証例の選択であり、利用者がactive-activeを指定したという扱いにはしない。

東京・大阪を一枚に描くMulti-Region主図を入口とする。Web三層、IoT処理、画面更新、非同期処理、監視の5図は補助図で、主図の同じサービスを詳細化・再掲する。主図のLambdaはRules→Kinesis→処理とStreams→画面配信を代表する記号で、両方向の線はまとめた論理経路である。補助図で実際のサービスと方向を確認する。主図のECS記号はAPI/ワーカー群の2AZ配置を表す。SQSとの双方向線はAPIのOutbox発行→EventBridge→SQSとワーカー取得をまとめた経路で、実際のサービスと方向は非同期補助図に示す。左右のブラウザは同じSPAクライアントの通常接続と切替後を再掲し、logical_id=web-clientを付ける。IoTデバイスは別の記号として、通常接続と再接続を描く。

## Web三層

静的配信はブラウザ→CloudFront→非公開S3の通常のバケットオリジンとし、OACでアクセスを制限する。S3 website endpointは使わない。AWS WAFはCloudFrontに関連付ける。図の関連付け線は通信の中継を意味しない。[AWSのOAC仕様](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)

APIは別のapi用ホスト名でALBへ接続する。ALBは複数AZの公開サブネット、ECS Fargateタスクは各AZの非公開アプリサブネットへ配置する。図のALBはAZをまたぐ論理リソースである。Fargateのターゲットグループはip型を使い、タスクのAZ配置・desired count・AZ rebalancingを確認する。PrivateタスクからAWS APIへ出るためのVPCエンドポイントまたはAZごとのNATを設計する。これらのネットワーク詳細は図の主要経路から省略している。[ECSのAZ分散](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-rebalancing.html)、[ECSとALB](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/alb.html)

## IoTと画面更新

デバイスはMQTT over TLSとX.509証明書でIoT Coreへ接続する。IoTルールはKinesis Data Streamsへ送信し、Lambdaが検証・冪等な集計を行ってDynamoDBの最新状態を更新する。別のルールでData Firehoseへ送り、S3に履歴を保存し、Athenaで分析する。Kinesisのpartition keyはdeviceIdなどの必要な順序単位とし、全体の厳密な順序を保証すると説明しない。[IoTの通信方式](https://docs.aws.amazon.com/iot/latest/developerguide/protocols.html)、[IoTルールの送信先](https://docs.aws.amazon.com/iot/latest/developerguide/iot-rule-actions.html)

画面更新はDynamoDB Streams→Lambda→IoT Coreの画面用トピック→ブラウザとする。DBからIoTへ直接送信する線は描かない。Cognito User Poolまたは連携IdPでユーザーを認証し、Identity PoolとIAMロールで一時的なAWS認証情報を取得する。認証済みCognito identityにはIAM側の権限とIoT Coreポリシーの両方を設定し、SigV4でMQTT over WSSへ接続する。CloudFrontの静的配信を経由するMQTT通信として描かない。アプリケーションデータは処理後の画面用トピックへ発行し、デバイスの生トピックへの購読権限は与えない。[IoTのWSS認証仕様](https://docs.aws.amazon.com/iot/latest/developerguide/protocols.html)、[Cognito identityの認可](https://docs.aws.amazon.com/iot/latest/developerguide/cog-iot-policies.html)

Lambdaのストリーム処理やメッセージ再送には重複を想定し、イベントID・デバイスのシーケンス番号・更新条件で冪等性を保つ。ブラウザは古い更新を採用せず、再接続後にECS APIから最新状態を取得する。exactly-once配送や永続的な接続継続を保証する構成ではない。[DynamoDB StreamsのLambda処理](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.Lambda.BestPracticesWithDynamoDB.html)

## 非同期処理

ECS APIの業務更新はAuroraとOutboxに記録し、Outbox発行処理からEventBridge→SQS→ECS Fargateワーカーへ渡す。非同期図のAPI記号は、Web図のAPI／発行処理を論理的に再掲している。Outboxテーブル・発行処理・重複防止の実装が必要で、図に線を引くだけでトランザクション整合性が成立するとは扱わない。

ワーカーはSQSを長期ポーリングし、visibility timeout、再試行、冪等性キーを設定する。処理失敗はDLQへ隔離し、原因確認後に再処理する。処理結果はDynamoDBへ更新し、Streams→Lambda経由で画面へ通知する。SQSやEventBridgeがリージョン間で自動複製されるとは描かない。

## データの使い分け

| 用途 | 選択 | 整合性・DRで確認する点 |
| --- | --- | --- |
| 業務トランザクション、関連データ、Outbox | Aurora PostgreSQL | 主系Writer、別AZ Reader。Global Databaseの副系はReaderで、昇格前の更新先にしない |
| デバイス最新状態、冪等性キー、処理結果 | DynamoDB Global Tables | この例はMREC。非同期複製・競合・遅延を想定し、デバイス番号と更新条件を設計 |
| 生データ・履歴・分析用Parquet | S3＋Athena | SPAと履歴は別バケット。CRRは非同期で、versioning、暗号鍵、複製失敗の監視が必要 |

Auroraはインスタンスごとに記号を置く。東京はAZ-AにWriter、AZ-CにReader、大阪は二つのAZにReaderを置く。大阪の一つがWriterへ昇格した後も別AZのReaderを維持する。AZ-A/Cは各リージョン内の論理名で、実際のAZ IDやサブネットは配備時に対応付ける。クラスター共有ストレージの3AZへの自動複製は注記し、Writer→Readerの直接複製線は描かない。DynamoDBはリージョナルなマネージドサービスとして描き、利用者のアプリ用AZに所属させない。FirehoseでParquetへ変換する場合は、入力形式、AWS Glue Data Catalogのスキーマ、変換設定、必要な権限を別途準備する。[Firehoseの形式変換](https://docs.aws.amazon.com/firehose/latest/dev/record-format-conversion.html)[Aurora Global Database](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html)、[DynamoDB Global Tables](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GlobalTables.html)

## Multi-Regionの切替

両リージョンにALBと2AZのECS Fargateサービスを用意し、待機系は必要な最小規模を維持する。Auroraの複製・昇格状態を確認してからAPIのDNSを切り替え、待機系の更新処理を有効化する。副系を昇格前から通常のWriterとして扱わない。Route 53の切替だけでDBや接続中のセッションが引き継がれるとは扱わない。

CloudFrontのorigin failoverは静的配信のS3 origin groupに使えるが、GET／HEAD／OPTIONSが対象である。POST／PUTなどのAPI更新をこの仕組みで自動切替すると説明しない。[CloudFrontのorigin failover制約](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/RequestAndResponseBehaviorOriginGroups.html)

IoT Coreのエンドポイント、証明書・ポリシー、Kinesis／Firehose、キュー、Cognitoの認証設定はリージョン別に設計・準備する。デバイスとブラウザには接続先の選択、再認証・再接続、状態再取得が必要である。Cognito user poolが自動的に別リージョンへ複製されるという前提は置かない。認証のDR方式とフェデレーションは、アプリケーションの具体化時に確定する。

この設計例はRTO／RPOを数値で保証しない。許容遅延、データ損失、重複、再処理範囲、切替の承認・自動化、バックアップ復旧を定め、実環境の障害試験で確認する必要がある。主図のS3はSPAバケットで、両リージョンの非公開バケットへOACでアクセスする。履歴用S3/Firehose/AthenaはIoT補助図で詳細化し、両地域への配備を別途設計する。主図のSQL線は両AZからWriter endpointへ接続し、副系は昇格後という条件を付ける。Global Databaseの線は共有ストレージ間の複製を代表インスタンスに接続した論理表現であり、WriterからReaderへの直接通信を意味しない。ブラウザ→ALBのHTTPS API通信を直接描く。ブラウザとRoute 53の線は名前解決の関連付けで、API通信の中継ではない。APIへ到達したECSからWriterへの更新とReaderへの参照を描く。読取経路は同一ECSサービスの代表経路で、AZごとにAPI機能を分割する指定ではない。

## 監視とセキュリティ

各リージョンでCloudWatch Logs／Metrics／Alarmsを収集し、SNSで運用担当者へ通知する。ECS Container Insights、IoTログ、ストリーム遅延、Lambdaエラー、SQS最古メッセージ年齢・DLQ件数、DB複製遅延などを、必要な設定を有効化して監視する。IoTやECSのログが設定なしで全て取得できるとは説明しない。

最小権限のIAM・IoTポリシー、テナント別topic、証明書の登録・失効、一時認証情報、TLS、S3の非公開設定、暗号化と鍵、Secrets Manager等でのアプリ秘密情報の管理を具体化する。図の検査は、これらのポリシーの正しさを証明しない。Well-Architectedの観点で一般的なパターンを採用した例であり、正式なWell-Architectedレビュー完了の宣言ではない。

## 図の確認と契約

主図の構成JSONにはavailability契約を付ける。主系/待機系、両地域のサービス、Fargateの2AZとALB接続、Auroraの役割・AZ・DB用サブネット、通常/切替の入口、S3/Aurora/DynamoDBのリージョン間複製と方向を検査する。これは宣言された構成の整合性検査であり、AWSの設定・稼働・障害時動作の証明ではない。

Web詳細図ではブラウザのSPA取得とAPI呼出しを別の実通信として描き、CloudFront→S3を短い水平線にし、DynamoDBへの二つのAZからの接続を上側と左側へ分ける。全ての接続は端点に24pt以上の直線を確保し、実描画で矢じりの余白を確認する。両テーマで、DB配置、リージョン枠、文字、配線、接続ラベル、縮小時と拡大時の読みやすさ、VPC枠との離隔を確認する。

## 0.6.0の構成正本

現行の推奨例はexamples/projects/modern-web-iot.json。API/ワーカー、IoT処理/画面配信を分離し、Outboxリレー、EventBridge、キュー発行・取得、クラスタ単位の複製を明示する。examples/real-worldの単独例は互換性・描画回帰の検査にも使う。主図の省略表現をそのまま新しい正式運用図へ転用しない。

## WebRTCの映像

Kinesis Video Streams with WebRTCではシグナリング、STUN、TURNと映像の経路を区別する。直接接続できるP2Pの図では送信側から視聴側へ映像の線を引き、KVSにはシグナリングの線を引く。直接接続できない場合はTURN中継になるため、必要なら経路や条件を示す。[AWSの構成説明](https://docs.aws.amazon.com/kinesisvideostreams-webrtc-dg/latest/devguide/kvswebrtc-how-it-works.html)

WebRTC ingestion and storageを使う構成ではクラウドへの映像取込もある。全てのWebRTC構成をP2Pだけで表さず、依頼された利用方式に合わせる。[AWSの取込・保存仕様](https://docs.aws.amazon.com/kinesisvideostreams-webrtc-dg/latest/devguide/getting-started-ingestion.html)
