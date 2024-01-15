# 要渲染html必需引入render_template,且所有html檔案都必須要放在templates資料夾內
# g是一個物件可以用來儲存資訊
from flask import Flask, render_template, request, g, redirect
from mysql.connector import Error
import mysql.connector, requests, math

app = Flask(__name__)

# 資料庫連線
def get_db():
    if not hasattr(g, "mysql_db"):
        try:
            g.mysql_db = mysql.connector.connect(
                host = "localhost",
                database = "financial",
                user = "root",
                password = "a0928125162"
            )
        except Error as e:
            print("資料庫連線失敗.", e)
            g.mysql_db = None
    return g.mysql_db

@app.route("/")
def home():
    # 從資料庫拿現金庫存表單資料
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
                    SELECT * FROM `cash`
                   """)
    # 現金更動紀錄  
    cash_result = cursor.fetchall()
    # 計算台幣和美金總額
    taiwanese_dollars = 0
    us_dollars = 0
    for data in cash_result:
        # 台幣在`cash`表的第二欄所以是index[1],美金是index[2]
        taiwanese_dollars += data[1]
        us_dollars += data[2]
    # 獲取匯率資訊
    r = requests.get('https://tw.rter.info/capi.php')
    currency = r.json()
    # currency["USDTWD"]["Exrate"]是api裡dic的東西,也就是key值就可以獲取即時匯率
    total = math.floor(taiwanese_dollars + us_dollars * currency["USDTWD"]["Exrate"])
    data = {"total":total,
            "currency":currency["USDTWD"]["Exrate"],
            "ud":us_dollars,
            "td":taiwanese_dollars,
            "cash_result":cash_result}
    # data物件取得上方data{}裡的值
    return render_template("index.html", data = data)

@app.route("/cash")
def cash_form():
    return render_template("cash.html")

@app.route("/cash", methods = ["post"])
def submit_cash():
    # 取得金額和日期資料,values[]是抓取html name的值
    taiwanese_dollars = 0
    us_dollars = 0
    if request.values["taiwanese-dollars"] != "":
        taiwanese_dollars  = request.values["taiwanese-dollars"]
    if request.values["us-dollars"] != "":
        us_dollars = request.values["us-dollars"]
    note = request.values["note"]
    date = request.values["date"]
    
    # 更新資料庫資料
    conn = get_db()
    cursor = conn.cursor()
    # 第二個()放上方submit_cash的變數
    cursor.execute("""
                   INSERT INTO `cash` (taiwanese_dollars, us_dollars, note, date_info)
                   values (%s, %s, %s, %s)
                   """, (taiwanese_dollars, us_dollars, note, date))
    conn.commit()
    # 將使用者導向首頁
    return redirect("/")

@app.route("/stock")
def stock_form():
    return render_template("stock.html")

@app.route("/stock", methods = ["post"])
def submit_stock():
    return 

if __name__ == "__main__":
    app.run(debug = True)