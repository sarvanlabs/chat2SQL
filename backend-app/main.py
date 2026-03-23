from fastapi import FastAPI

app = FastAPI(title='Chat2SQL')

@app.get('/')
def root():
    return {"message": "Welcome to Chat2SQL"}

