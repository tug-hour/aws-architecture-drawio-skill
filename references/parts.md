# 部品の作成・複製・移動

`parts.py`は展開済みの`drawio/1`を編集する任意のPython APIである。各関数は`(更新後の辞書, 操作結果)`を返し、入力を変更しない。操作結果の`ids`はIDの対応、`affected_edges`は局所調整が必要な外部接続のIDである。JSONを直接編集する方法も継続できる。

部品は選択した頂点と、その子の記号・名称・役割・枠である。部品内の両端を結ぶ線も、線のparentの位置にかかわらず内部接続として扱う。図の意味、所属や通信方向を推測して変更しない。展開済みJSONを維持する理由は[設計判断](adr-expanded-parts.md)に記録する。

| API | 指定と動作 |
| --- | --- |
| `add_part(doc, id, at=(x,y), asset=..., ...)` | カタログの寸法・色・標準図形を初期値として部品を作る。`name`・`role`・`parent`・`theme`を指定できる。カタログ外は`shape`・`color`・`kind`・`size`で明示でき、未登録を理由に標準図形を禁止しない |
| `copy_part(source, roots, prefix=..., target=..., parent=..., offset=(dx,dy))` | rootsはID一つ、または複数ID。子要素と内部接続を複製する。ルートの位置は最初の選択ルートの親からの相対座標にoffsetを足し、複製先parentへ置く。parent省略時は元の親、target省略時は同じ図へコピーする |
| `move_part(doc, roots, offset=(dx,dy), parent=...)` | 選択部品を絶対pxで平行移動する。parentを指定すると、画面上の移動量を保って親を変更する。内部経由点を一度だけ移動し、外部経由点の絶対位置を保つ |

作成時の既定値はJSONへ展開して保存し、再生成時には適用し直さない。生成後の文字領域・接続点・経由点は直接修正できる。カタログの暫定値はPPTXへの適合確認を代替しない。必要な正式名・改行は`name`で指定する。

複製ではIDとparent・source・targetを対応付け、同名で内容が異なるスタイルも別名にする。外部接続は複製せず、対象一覧を返す。更新する子要素は実データや操作結果の`ids`から特定し、役割ラベルなどの存在を仮定しない。再利用で用途が変わる名称・役割・枠見出しは、複製時にまとめて更新する。移動では外部接続の端点が追従するが、経由点からの引き直しは行わない。`affected_edges`とその周辺を調整する。無関係な要素の位置・順序・スタイルを変更しない。

ID衝突、不明な親、循環、非有限座標は操作を中止する。入力辞書と既存ファイルは変更しない。これはデータ保護のための扱いであり、図形の種類や交差数による受付制限ではない。

使用例は説明用のPythonであり、永続的な第二の更新元ではない。`<skill-dir>`をスキルの絶対パスへ置き換える。

```python
import json
import sys
from pathlib import Path
sys.path.insert(0, '<skill-dir>/scripts')
from parts import add_part, copy_part, move_part

source = json.loads(Path('architecture.json').read_text())
source, created = add_part(source, 'key', asset='aws4.key_management_service',
                           name='AWS Key Management Service', role='暗号化',
                           parent='region', at=(500, 300))
source, copied = copy_part(source, 'key', prefix='copy.', offset=(300, 0))
source, moved = move_part(source, 'copy.key', offset=(0, 150))
with Path('architecture-next.json').open('x') as stream:
    stream.write(json.dumps(source, ensure_ascii=False, indent=2) + '\n')
```

接続は`key.icon`など実際の端点へ結ぶ。作成した部品のIDは操作結果に含まれ、複製後の端点は`copied['ids']['key.icon']`で取得できる。図形の下の名称・役割と配線の領域は[配置と経路](layout-and-routing.md)に従って選ぶ。生成・描画と任意の診断の条件・コマンドは[rendering.md](rendering.md)に集約する。
