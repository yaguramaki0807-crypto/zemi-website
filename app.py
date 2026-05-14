import os
import requests
from flask import Flask, request, render_template
from google import genai

app = Flask(__name__)

client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY")
)

# 画像解析用
SYSTEM_PROMPT = """
画像を見て以下を読み取ってください：

1. 売電量
2. 蓄電量
3. 発電量
4. 消費量
5. 日付けと時間

読み取った情報を簡潔にまとめてください。
"""

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():

    # 画像取得
    image = request.files["image"]
    img_bytes = image.read()

    # =========================
    # ① Geminiで画像解析
    # =========================
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            SYSTEM_PROMPT,
            {
                "inline_data": {
                    "mime_type": image.mimetype,
                    "data": img_bytes
                }
            }
        ]
    )

    image_result = response.text

    # =========================
    # ② 仮の天気データ
    # =========================
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
    "latitude": 35.5011,   # 鳥取市
    "longitude": 134.2351,
    "daily": "weathercode",
    "timezone": "Asia/Tokyo"
}

    weather_response = requests.get(
    url,
    params=params,
    timeout=5
)

    weather_data = weather_response.json()

    weather_code = weather_data["daily"]["weathercode"][0]

    # 天気コード変換
    weather_map = {
    0: "快晴",
    1: "晴れ",
    2: "曇り",
    3: "曇り",
    61: "雨",
    63: "強い雨",
    80: "にわか雨"
}

    weather = weather_map.get(weather_code, "不明")
    # =========================
    # ③ 天気込みで再分析
    # =========================
    analysis_prompt = f"""
以下が画像解析結果です。

{image_result}


画像を見て以下を読み取ってください：
1. 売電量 
2. 蓄電量（待機となっているところ）
3. 発電量
4. 消費量
5. 日付けと時間

天気APIによって2026年の読み取られた日付の鳥取市の天気は
「{weather}」であると確認されました。
以降は説明。
太陽が多く出ているときは発電量が多くなる。すると余った電気を電力会社に売るという行為をおこなったり、蓄電量をためたりする。逆に太陽が出ていないとき（夜や雨、曇りの日など）の時は、
発電量が足りないので電気を売るのをやめて蓄電量から足りない分を賄うなど環境を考えAIが自動で4つの電力量を調整してくれるシステムがある。
そこでなぜこの画像の日にこの電量の制御を行っているのかを各発電量を見て分析してもらいたい。
また、天気APIによって得たその日の天気も考慮して分析してもらいたい。
下のテンプレの通りに出力してね。
テンプレ:
発電量 1200W (4月23日の日中はは晴れのために発電量が多い)
消費量 600W  
売電量 600W  (発電量のうち余った分の電力を電力会社に売っている)
蓄電量 no use [充電100%] (発電量が十分に足りているため蓄電量は利用していない)

まとめ
4月23日の日中は晴れのため発電量が多く余った分を電力会社に売っている。また蓄電からは発電量が充電なため電量は賄われていない。
（もし蓄電量が使われていたら何W分を賄っているか書いてね。）

＊数値が読めとれなかった時のテンプレ:
数値が読み取れませんでした。もう一度画像を送信してください。
"""

    final_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=analysis_prompt
    )

    # =========================
    # ④ 結果表示
    # =========================
    return render_template(
        "index.html",
        result=final_response.text
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)