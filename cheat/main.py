from flask import Flask

code=open("code.txt","r",encoding="utf-8").readlines()
text="<!doctype><html><head></head><body>"
for line in code:
    text+="<p>"+str(line)+"</p>"
text+="</body></html>"
app=Flask(__name__)
@app.route("/")

def index():
    return text
if __name__=="__main__":
    app.run(host="0.0.0.0",port=1145,debug=True)
