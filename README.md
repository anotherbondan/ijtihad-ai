1. Clone repository (On terminal)
``` bash
git clone https://github.com/anotherbondan/ijtihad-ai.git
```

2. Create new branch on root directory (ex. ChatbotAPI)
```bash
git checkout -b ChatbotAPI
```

3. Pull any latest changes in dev
```bash
git pull origin dev
```

3. Create virtual environment
```bash
python -m venv env
.\env\Scripts\activate
```

4. Install package
```bash
pip install fastapi uvicorn jinja2 python-multipart scikit-learn joblib
```

5. Run app 
```bash
uvicorn main:app --reload
```

6. Open in browser (add /docs to see API docs)
```bash
http://127.0.0.1:8000
```

5. Make changes, add and commit as usual, then push the branch
```bash
git add .
git commit -m "create something"
git push origin ChatbotApi
```




