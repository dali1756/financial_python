# 要渲染html必需引入render_template,且所有html檔案都必須要放在templates資料夾內
# g是一個物件可以用來儲存資訊,確保flask應用一次請求多次資料庫時只需建立一次連接
from flask import Flask, render_template, request, g, redirect
from mysql.connector import Error
import mysql.connector, requests, math

app = Flask(__name__)

# 資料庫連線
def get_db():
    if not hasattr(g, "mysql_db"):
        try:
            g.mysql_db = mysql.connector.connect(
                
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
    # total = math.floor(taiwanese_dollars + us_dollars * currency["USDTWD"]["Exrate"])
    total = round(taiwanese_dollars + us_dollars * currency["USDTWD"]["Exrate"], 2)
    # 取得使用者儲存股票資訊
    cursor.execute("""
                   SELECT * FROM `stock`
                   """)
    stock_result = cursor.fetchall()
    # 購買的股票種類,用stock_id股票代號分類
    unique_stock_list = []
    for data in stock_result:
        # data[1]是stock_result的資料裡第一項,就是stock_id股票代號
        if data[1] not in unique_stock_list:
            unique_stock_list.append(data[1])
    # 計算市值
    total_stock_value = 0
    # 計算單一股票資訊
    stock_info = []
    for stock in unique_stock_list:
        # 後方()中如果只有一個參數必需要在結尾加上 , 才不會被認為是元素而是元組tup
        cursor.execute("""
                        SELECT * FROM `stock` WHERE stock_id = %s
                       """, (stock,))
        result = cursor.fetchall()
        # 單一股票總額
        stock_cost = 0
        # 單一股票股數
        shares = 0
        for new_stock in result:
            shares += new_stock[2] # 股數是在index[2]
            # 股數*單價+手續費+交易稅
            stock_cost += new_stock[2] * new_stock[3] + new_stock[4] + new_stock[5]
            # 取得目前股價api,後方+的stock是從unique_stock_list來的
            url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&stockNo=" + stock
            response = requests.get(url) 
            data = response.json()
            # 找最近購買的成交價.收盤價等資訊,print(data)後會發現在data list裡
            price_array = data["data"]
            # 個檔股票價格,資料是str要改用float才能使用index[]做計算
            current_price = float(price_array[len(price_array) - 1][6])
            # 單一股票總市值,取到小數點第二位
            total_value = round(current_price * shares, 2)
            total_stock_value += total_value
            # 單一股票平均成本,取到小數點第二位
            average_cost = round(stock_cost / shares, 2)
            # 單一股票投報率
            rate_return = round((total_value - stock_cost) * 100 / stock_cost, 2)
            stock_info.append({
                "stock_id":stock,
                "stock_cost":stock_cost,
                "total_value":total_value,
                "average_cost":average_cost,
                "shares":shares,
                "current_price":current_price,
                "rate_return":rate_return
            })
    # 資產佔比
    for stock in stock_info:
        stock["value_percentage"] = round(stock["total_value"] * 100 / total_stock_value, 2)
    data = {"total":total,
            "currency":round(currency["USDTWD"]["Exrate"], 2),
            "ud":us_dollars,
            "td":taiwanese_dollars,
            "cash_result":cash_result,
            "stock_info":stock_info}
    # data物件取得上方data{}裡的值
    return render_template("index.html", data = data)

# 現金庫存
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
    
    # 更新cash資料表
    conn = get_db()
    cursor = conn.cursor()
    # 第二個()放上方submit_cash的變數,後方()中如果只有一個參數必需要在結尾加上 , 才不會被認為是元素而是元組tup
    cursor.execute("""
                   INSERT INTO `cash` (taiwanese_dollars, us_dollars, note, date_info)
                   values (%s, %s, %s, %s)
                   """, (taiwanese_dollars, us_dollars, note, date,))
    conn.commit()
    # 將使用者導向首頁
    return redirect("/")

# 股票庫存
@app.route("/stock")
def stock_form():
    return render_template("stock.html")

@app.route("/stock", methods = ["post"])
def submit_stock():
    # 取得股票資訊和日期資料
    stock_id = request.values["stock-id"] # 代號
    stock_num = request.values["stock-num"] # 股數
    stock_price = request.values["stock-price"] # 單價
    processing_fee = 0 # 手續費
    tax = 0 # 交易稅
    if request.values["processing-fee"] != "":
        processing_fee = request.values["processing-fee"]
    if request.values["tax"] != "":
        tax = request.values["tax"]
    date = request.values["date"] # 日期
    # 更新stock資料表
    conn = get_db()
    cursor = conn.cursor()
    # 後方()中如果只有一個參數必需要在結尾加上 , 才不會被認為是元素而是元組tup
    cursor.execute("""
                   INSERT INTO `stock` (stock_id, stock_num, stock_price, processing_fee, tax, date_info)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   """, (stock_id, stock_num, stock_price, processing_fee, tax, date,))
    conn.commit()
    return redirect("/")

# 刪除資料
@app.route("/cash-delete", methods = ["post"])
def cash_delete():
    # 這裡的id需要和index.html <form>表單中的name欄位相同
    transaction_id = request.values["id"]
    conn = get_db()
    cursor = conn.cursor()
    # SQL語法後的()內容需要在結尾加上 , 因為是tup關係,不加會有bug
    # 後方()中如果只有一個參數必需要在結尾加上 , 才不會被認為是元素而是元組tup,如是多參數可以不必在結尾加上 ,
    cursor.execute("""
                   DELETE FROM `cash` WHERE transaction_id = %s
                   """, (transaction_id,))
    conn.commit()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug = True)