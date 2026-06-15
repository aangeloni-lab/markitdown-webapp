import os
import tempfile
from pathlib import Path
from flask import Flask, request, send_file, render_template_string
from markitdown import MarkItDown
from openai import OpenAI

app = Flask(__name__)
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
md = MarkItDown(llm_client=openai_client, llm_model="gpt-4o")

HTML = """
<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <title>MarkItDown Converter</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0f0f0f;
      color: #e0e0e0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 40px 20px;
    }
    h1 { font-size: 1.4rem; font-weight: 500; margin-bottom: 8px; color: #fff; }
    p.sub { font-size: 0.85rem; color: #666; margin-bottom: 40px; }
    #drop-zone {
      width: 100%; max-width: 540px;
      border: 2px dashed #333; border-radius: 16px;
      padding: 60px 40px; text-align: center; cursor: pointer;
      transition: border-color 0.2s, background 0.2s;
    }
    #drop-zone.hover { border-color: #555; background: #1a1a1a; }
    #drop-zone .icon { font-size: 2.5rem; margin-bottom: 16px; }
    #drop-zone .label { font-size: 1rem; color: #aaa; }
    #drop-zone .formats { font-size: 0.75rem; color: #555; margin-top: 10px; }
    #file-input { display: none; }
    #status { margin-top: 32px; width: 100%; max-width: 540px; display: flex; flex-direction: column; gap: 10px; }
    .file-row {
      background: #1a1a1a; border-radius: 10px; padding: 14px 18px;
      display: flex; align-items: center; justify-content: space-between; font-size: 0.85rem;
    }
    .file-row .name { color: #ccc; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .badge { font-size: 0.75rem; padding: 3px 10px; border-radius: 20px; margin-left: 12px; white-space: nowrap; }
    .badge.ok { background: #1a3a1a; color: #4caf50; }
    .badge.err { background: #3a1a1a; color: #f44336; }
    .badge.wait { background: #2a2a1a; color: #aaa; }
    #download-btn {
      margin-top: 24px; padding: 12px 32px; background: #fff; color: #000;
      border: none; border-radius: 10px; font-size: 0.9rem; font-weight: 600;
      cursor: pointer; display: none; transition: opacity 0.2s;
    }
    #download-btn:hover { opacity: 0.85; }
  </style>
</head>
<body>
  <h1>MarkItDown Converter</h1>
  <p class="sub">Converti documenti e immagini in Markdown per LLM</p>
  <div id="drop-zone" onclick="document.getElementById('file-input').click()">
    <div class="icon">📄</div>
    <div class="label">Trascina i file qui oppure clicca per selezionarli</div>
    <div class="formats">PDF · DOCX · PPTX · XLSX · EPUB · HTML · TXT · CSV · JPG · PNG · HEIC</div>
  </div>
  <input type="file" id="file-input" multiple>
  <div id="status"></div>
  <button id="download-btn" onclick="downloadZip()">Scarica tutti i file .md</button>
  <script>
    const zone = document.getElementById('drop-zone');
    const status = document.getElementById('status');
    const dlBtn = document.getElementById('download-btn');
    let convertedFiles = [];
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('hover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('hover'));
    zone.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('hover'); handleFiles(e.dataTransfer.files); });
    document.getElementById('file-input').addEventListener('change', e => handleFiles(e.target.files));
    async function handleFiles(files) {
      status.innerHTML = ''; dlBtn.style.display = 'none'; convertedFiles = [];
      for (const f of Array.from(files)) {
        const row = document.createElement('div');
        row.className = 'file-row';
        row.innerHTML = '<span class="name">' + f.name + '</span><span class="badge wait">Conversione...</span>';
        status.appendChild(row);
        const formData = new FormData();
        formData.append('file', f);
        try {
          const res = await fetch('/convert', { method: 'POST', body: formData });
          if (res.ok) {
            const blob = await res.blob();
            const mdName = f.name.replace(/\.[^.]+$/, '') + '.md';
            convertedFiles.push({ name: mdName, blob });
            row.querySelector('.badge').className = 'badge ok';
            row.querySelector('.badge').textContent = '✓ Convertito';
          } else {
            row.querySelector('.badge').className = 'badge err';
            row.querySelector('.badge').textContent = 'Errore';
          }
        } catch {
          row.querySelector('.badge').className = 'badge err';
          row.querySelector('.badge').textContent = 'Errore';
        }
      }
      if (convertedFiles.length > 0) dlBtn.style.display = 'block';
    }
    async function downloadZip() {
      if (convertedFiles.length === 1) {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(convertedFiles[0].blob);
        a.download = convertedFiles[0].name;
        a.click();
        return;
      }
      const { default: JSZip } = await import('https://cdn.jsdelivr.net/npm/jszip@3.10.1/+esm');
      const zip = new JSZip();
      for (const f of convertedFiles) zip.file(f.name, f.blob);
      const blob = await zip.generateAsync({ type: 'blob' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'markdown_files.zip';
      a.click();
    }
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/convert', methods=['POST'])
def convert():
    f = request.files.get('file')
    if not f:
        return 'Nessun file ricevuto', 400
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(f.filename).suffix) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name
    try:
        result = md.convert(tmp_path)
        out = tempfile.NamedTemporaryFile(delete=False, suffix='.md', mode='w', encoding='utf-8')
        out.write(result.text_content)
        out.close()
        md_name = Path(f.filename).stem + '.md'
        return send_file(out.name, as_attachment=True, download_name=md_name, mimetype='text/markdown')
    except Exception as e:
        return str(e), 500
    finally:
        os.unlink(tmp_path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(debug=False, host='0.0.0.0', port=port)
