from dotenv import load_dotenv
import os
import requests
from flask import Flask, request, render_template
from google import genai
import base64
import json
from datetime import datetime


app = Flask(__name__)
load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
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

    img_base64 = base64.b64encode(img_bytes).decode("utf-8")

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
    # =========================
# ② 気象庁データ取得（1日キャッシュ）
# =========================

    weather_file = "weather.json"

    today = datetime.now().strftime("%Y-%m-%d")

    weather = None

# 保存済み確認
    if os.path.exists(weather_file):

        with open(weather_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

    # 今日のデータなら再利用
        if saved_data["date"] == today:
            weather = saved_data["weather"]

# 今日のデータが無いならAPI取得
    if weather is None:

        url = "https://www.jma.go.jp/bosai/forecast/data/forecast/310000.json"

        response = requests.get(url, timeout=5)

        data = response.json()

        weather = data[0]["timeSeries"][0]["areas"][0]["weathers"][0]

    # 保存
        with open(weather_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "date": today,
                    "weather": weather
                },
                f,
                ensure_ascii=False
            )
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

天気APIによって読み取られた日付の鳥取市の天気は
「{weather}」であると確認されました。
以降は説明。
太陽が多く出ているときは発電量が多くなる。すると余った電気を電力会社に売るという行為をおこなったり、蓄電量をためたりする。逆に太陽が出ていないとき（夜や雨、曇りの日など）の時は、
発電量が足りないので電気を売るのをやめて蓄電量から足りない分を賄うなど環境を考えAIが自動で4つの電力量を調整してくれるシステムがある。
そこでなぜこの画像の日にこの電量の制御を行っているのかを各発電量を見て分析してもらいたい。
また、天気APIによって得たその日の天気も考慮して分析してもらいたい。
下のテンプレの通りに出力してね。
テンプレ:
発電量 1200W 
(4月23日の日中はは晴れのために発電量が多い)
消費量 600W  
売電量 600W  
(発電量のうち余った分の電力を電力会社に売っている)
蓄電量 no use [充電100%] 
(発電量が十分に足りているため蓄電量は利用していない)

まとめ
4月23日の日中は晴れの予報のため発電量が多く余った分を電力会社に売っている。また蓄電からは発電量が充電なため電量は賄われていない。
（もし蓄電量が使われていたら何W分を賄っているか書いてね。）

＊数値が読めとれなかったり明らかに発電量とは関係のない画像だったときの時のテンプレ:
数値が読み取れませんでした。もう一度画像を送信してください。
"""

    try:

        final_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=analysis_prompt
        )

        result_text = final_response.text

    except Exception as e:

        print(e)

        result_text = "現在AIサーバーが混雑しています。時間を置いて再度お試しください。"

    # =========================
    # ④ 結果表示
    # =========================
    return render_template(
    "index.html",
    result=result_text,
    image_data=img_base64,
    mime_type=image.mimetype
)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)