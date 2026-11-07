# JSONからの作成と更新

既存Pythonの標準ライブラリで原本を生成し、既存draw.ioで表示する。新規導入や設定変更を行う処理はない。以下の`<skill-dir>`はこのスキルのルート、出力先は未作成のフォルダ・ファイルに置き換える。

## 入力と生成

JSONは既存の`drawio/1`を使う。構成・配置・文字・接続の指定値を保存する形式で、自動配置やテーマ変換はしない。通常の生成入口は一つである。

```sh
python3 -B "<skill-dir>/scripts/build_drawio.py" --input "<drawing.json>" --output "<new-directory>"
```

新しいフォルダにarchitecture.json・diagram.drawio・report.jsonを保存する。既存の入力・出力は上書きしない。`status=authored`と秒数は原本生成の結果だけで、配置の検討や描画確認を含まない。

```json
{
  "format": "drawio/1",
  "page": {"id": "drawing", "name": "構成", "model": {"background": "#FFFFFF"}},
  "styles": {"wire": {"strokeColor": "#000000", "strokeWidth": 1.6667, "endArrow": "open", "endFill": 0, "endSize": 6}},
  "elements": {
    "a": {"parent": "1", "bounds": [100,100,80,80], "overrides": {"group": null}, "connectable": false},
    "b": {"parent": "1", "bounds": [400,100,80,80], "overrides": {"group": null}, "connectable": false},
    "ab": {"source": "a", "target": "b", "style": "wire", "source_port": [1,0.5], "target_port": [0,0.5], "waypoints": []}
  }
}
```

これは座標・接続の構造例であり、AWS記号は下記の部品操作で追加できる。elementsは安定IDをキーにする。記号・枠・文字はbounds=[x,y,width,height]、文字はvalue、共通書式はstylesとstyle、個別書式はoverrides。parent省略時はページの`1`で、子座標は親に対する相対px。shapeにはdraw.ioの標準図形IDを直接指定できる。JSONの重複キー・不明参照・循環・非有限座標など生成不能な入力はエラーになるが、図形一覧や配線品質で入力を拒否しない。

線はsource・targetを実際の端点へ結ぶ。source_port・target_portは各辺上の相対位置、waypointsは線のparentからの相対px。ポートを省略すればdraw.ioの接続解決に委ねられるが、経路を固定して更新したい線では採用値を明示する。既存線を別の変更に伴って再配置しない。細かなラベル位置や線のstyleもJSONで直接編集できる。

## 複数の変更をまとめる

通常の部品操作・文言変更・接続変更は操作配列へまとめ、同じ生成入口へ渡せる。JSONを直接編集する従来の方法も使える。

```sh
python3 -B "<skill-dir>/scripts/build_drawio.py" --input "<drawing.json>" --operations "<operations.json>" --output "<new-directory>"
```

```json
[
  {"op":"copy", "roots":["key"], "prefix":"copy.", "offset":[300,0]},
  {"op":"set", "id":"copy.key.name", "fields":{"value":"AWS Key Management Service"}},
  {"op":"move", "roots":["copy.key"], "offset":[0,150]}
]
```

操作は配列順に適用する。addはid・atと既存add_partの指定、copy／moveはrootsと既存の引数を使う。setは既存要素の指定フィールドを更新する（overrides等の辞書はフィールド全体を置換する）。putはid・elementで新規のdrawio/1要素や接続を追加し、removeはidで要素を除去する。参照の整合性は操作配列の適用後に確認する。操作結果にはID対応と影響する外部線を返す。文言の子IDは実データまたは直前のID対応から選ぶ。操作ファイルは編集の入力であり、再生成は出力されたarchitecture.jsonだけで行える。

対象部品・関連線・必要な親枠以外の保存値は変更しない。移動時に外部線の端点は追従するが、経由点は絶対位置を保つため、必要な線だけ続けて調整する。setで親やboundsを直接変える場合は、子や経由点の座標変換はしない。まとまりの移動にはmoveを使う。処理途中で不正な参照などが生じた場合は、入力を変更せず生成を失敗させる。図形の種類や配線品質で入力を拒否する処理は追加しない。

規則の既定値は部品作成時だけ使い、採用値をJSONへ展開する。生成時に既存図へ再適用しない。整列・接続点・経路の計算支援は、対象を指定した操作として必要なものだけ使い、採用結果を保存する。生成するたびの自動配置は行わない。

## 部品を作る・再利用する

[CaseHub](../examples/casehub.json)は複数機能・2地域の構成例。接続関係が適合する部分の配置と内部配線を再利用し、例全体のサービス構成を依頼へ強制しない。

```python
import json, sys
from pathlib import Path
sys.path.insert(0, '<skill-dir>/scripts')
from parts import add_part, copy_part, move_part

source = json.loads(Path('<drawing.json>').read_text())
updated, created = add_part(source, 'key', parent='1', at=(500,300),
                            asset='aws4.key_management_service',
                            name='AWS Key Management Service', role='暗号化')
updated, copied = copy_part(updated, 'key', prefix='copy.', offset=(300,0))
updated, moved = move_part(updated, 'copy.key', offset=(0,150))
with Path('<new-drawing.json>').open('x') as stream:
    stream.write(json.dumps(updated, ensure_ascii=False, indent=2) + '\n')
```

各APIは入力を変えず、(更新後の辞書, 操作結果)を返す。このPythonは編集の例であり、永続的な第二の正本ではない。

- add_partはカタログを初期値として記号・名称・任意の役割をまとめて作る。未知の図形もshape・color・kind・sizeで指定できる。frameを明示して枠も作れる。初期値はJSONへ展開され、次の生成時に再適用しない。
- copy_partは選択頂点と子要素・内部接続を複製する。targetで別JSON、parentで所属先、offsetで移動量を指定できる。複製ルートは最初の選択ルートの親座標を基準に配置する。IDとスタイル衝突を解決し、外部接続は複製せず操作結果へ返す。
- move_partは選択部品と内部経由点を一度だけ平行移動する。parent指定で親も変更できる。外部線の端点は追従するが経由点は絶対位置を保つため、affected_edgesと周辺を必要な範囲で調整する。

更新する子要素は実データや操作結果のidsで特定し、任意のrole等が常に存在するとは仮定しない。用途が変わる名称・役割・枠見出しは複製時にまとめて更新する。実際の端点は作成例ではkey.icon、複製後はcopied['ids']['key.icon']。新しいJSONから別の出力先へ生成する。

記号の初期値が必要なときだけ検索する。

```sh
python3 -B "<skill-dir>/scripts/catalog.py" "<service-name>"
```

## 表示と任意の診断

通常は既存draw.ioのCLIでdiagram.drawioを一度だけPNGへ書き出し、その画像をSKILL.mdの範囲で目視する。同じ画像を確認と納品に使え、既存画像の拡大・切り出しで確認できる箇所は再描画しない。Computer Useでの連続したパン・ズーム・書き出し操作は通常手順にしない。GUIは依頼された原本の表示、直接編集、CLIでは確認できない箇所に絞る。

成功済みの実行環境と既存の専用profileを使い、同じprofileの書き出しは直列に実行する。CLIもDesktopの描画エンジンを使うため、OSの実行制限等で起動できない場合がある。確認済みの同条件の失敗を繰り返さず、承認済みの実行環境を使える場合はそこから実行し、使えない場合は既存GUIへ切り替える。起動方法の総当たり、設定変更、新しい描画基盤の導入は行わない。確認できない場合は描画未確認と伝える。

CLI書き出しの例（既存の専用profileを使う場合だけ）：

```sh
"<drawio>" --disable-update --user-data-dir="<existing-profile>" --export --format png --theme light --output "<new-image.png>" "<diagram.drawio>"
```

theme lightはエディターの色変換を防ぐ指定で、原本をライト図へ変換しない。SVGが必要ならformatをsvgとし`--embed-svg-fonts false`を指定する。GUI操作は利用可能なネイティブアプリ操作ツールを使う。

経路比較が判断に役立つ場合だけ、保存した原本を読み取り診断する。

```sh
python3 -B "<skill-dir>/scripts/drawio_routes.py" "<before.drawio>" "<candidate.drawio>"
```

既存の経路・衝突判定を再利用する読み取り処理で、原本や経路は変更しない。交差・折れ曲がり・延長と指摘を確認補助として返す。接続先が異なる候補を数値だけで比較せず、交差の移動と全体の読みやすさも見る。文字領域は保存寸法でありフォント実測ではない。自動経路・曲線などの未解析部分はunresolvedに残る。終了コード0は解析を実行できたことだけを示し、図の合格ではない。
