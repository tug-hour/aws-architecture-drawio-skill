"""架空のActive/Active構成。同じ配置・推定文字幅で、既定の辺＋自動経路は交差5・折れ22、指定の辺＋レーンは交差3・折れ20。
経路長は7598.0ptから8298.4ptへ増える。描画確認とは別の計算結果であり、最適性を保証しない。"""
POS = {'entry': (150, 550), 'api-a': (400, 300), 'api-c': (400, 800),
       'worker-a': (800, 300), 'worker-c': (800, 800), 'queue': (1100, 550),
       'state': (1400, 300), 'archive': (1400, 800)}
W = 1640
H = 1080
SIDES = {'entry-a': ('right', 'left'), 'entry-c': ('right', 'left'),
         'publish-a': ('right', 'left'), 'publish-c': ('right', 'left'),
         'poll-a': ('left', 'left'), 'poll-c': ('right', 'right'),
         'state-a': ('right', 'top'), 'state-c': ('top', 'left'),
         'save-a': ('right', 'left'), 'save-c': ('right', 'left')}
LANES = {'entry-a': [280], 'entry-c': [300],
         'publish-a': [560], 'publish-c': [580],
         'poll-a': [700], 'poll-c': [1240, 580],
         'state-a': [520, 200], 'state-c': [700, 1320],
         'save-a': [1280], 'save-c': []}
