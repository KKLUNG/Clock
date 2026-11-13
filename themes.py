"""變色模式：每個模式替每個時段定義一組左→右的漸層色，以及文字、陰影、進度條等顏色。

時段（palette）：morning 午休前、noon 午休、afternoon 午休後、lasthour 下班前一小時、
overtime 加班中、off 下班後、weekend 週末。
"""

THEMES = {
    "colorful": {
        "name": "繽紛",
        "palettes": {
            "morning": ("#3a7bd5", "#00d2ff"),
            "noon": ("#3a7bd5", "#00d2ff"),
            "afternoon": ("#f7971e", "#ffd200"),
            "lasthour": ("#ff0080", "#7928ca"),
            "overtime": ("#41295a", "#2f0743"),
            "off": "rainbow",  # 下班後彩虹流動
            "weekend": ("#11998e", "#38ef7d"),
        },
        "fg": "#ffffff", "shadow": "dark", "bar": "#ffffff", "border": None,
        "glow": ("#ffffff", "#ff66c4"), "sky": False,
    },
    "sky": {
        "name": "天空",
        "palettes": {
            "morning": ("#7fb6f5", "#f9b98e"),
            "noon": ("#1e88e5", "#6ec6ff"),
            "afternoon": ("#ff7e5f", "#8e44ad"),
            "lasthour": ("#e8505b", "#4b2a7b"),
            "overtime": ("#0f2027", "#2c5364"),
            "off": ("#141e30", "#243b55"),
            "weekend": ("#1e88e5", "#6ec6ff"),
        },
        "fg": "#ffffff", "shadow": "dark", "bar": "#ffffff", "border": None,
        "glow": ("#ffffff", "#ffd56b"), "sky": True,
    },
    "neon": {
        "name": "霓虹",
        "palettes": {
            "morning": ("#1a0533", "#0b1a4a"),
            "noon": ("#1a0533", "#0b1a4a"),
            "afternoon": ("#1a0533", "#0b1a4a"),
            "lasthour": ("#2a0845", "#0b1a4a"),
            "overtime": ("#12002b", "#050d2e"),
            "off": ("#1a0533", "#0b1a4a"),
            "weekend": ("#1a0533", "#0b1a4a"),
        },
        "fg": "#00f5ff", "shadow": "dark", "bar": "#ff2bd6", "border": "#ff2bd6",
        "glow": ("#ff2bd6", "#00f5ff"), "sky": False,
    },
    "pastel": {
        "name": "粉彩",
        "palettes": {
            "morning": ("#fbc2eb", "#a6c1ee"),
            "noon": ("#fdf6b5", "#bdf0f5"),
            "afternoon": ("#ffecd2", "#fcb69f"),
            "lasthour": ("#ff9a9e", "#fecfef"),
            "overtime": ("#a18cd1", "#fbc2eb"),
            "off": ("#84fab0", "#8fd3f4"),
            "weekend": ("#d4fc79", "#96e6a1"),
        },
        # 淺色底配白字看不清楚，改用深色字和淺色陰影
        "fg": "#4a3f5c", "shadow": "light", "bar": "#6d5a87", "border": None,
        "glow": ("#ffffff", "#ff6fa5"), "sky": False,
    },
    "lowkey": {
        "name": "低調",
        "palettes": {
            "morning": ("#2c2c2e", "#3a3a3c"),
            "noon": ("#2c2c2e", "#3a3a3c"),
            "afternoon": ("#2c2c2e", "#3a3a3c"),
            "lasthour": ("#ff0080", "#7928ca"),  # 只有最後一小時變色
            "overtime": ("#1c1c1e", "#2a2a2c"),
            "off": ("#2c2c2e", "#3a3a3c"),
            "weekend": ("#2c2c2e", "#3a3a3c"),
        },
        "fg": "#ffffff", "shadow": "dark", "bar": "#e5e5ea", "border": None,
        "glow": ("#ffffff", "#ff66c4"), "sky": False,
    },
    "ocean": {
        "name": "海洋",
        "palettes": {
            "morning": ("#3fd0c0", "#4a9fe0"),
            "noon": ("#2bb8d6", "#3b6fd8"),
            "afternoon": ("#1e3c72", "#2a5298"),
            "lasthour": ("#0b2d5b", "#00a7cf"),
            "overtime": ("#0f2027", "#203a43"),
            "off": ("#00a6e6", "#0062d9"),
            "weekend": ("#2fb38f", "#185a9d"),
        },
        "fg": "#ffffff", "shadow": "dark", "bar": "#ffffff", "border": None,
        "glow": ("#ffffff", "#7ff3ff"), "sky": False,
    },
}
