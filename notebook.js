const $ = id => document.getElementById(id);

// GitHub Pages project sites and account sites both work without a build step.
// Explicit settings also support custom domains, docs/ roots, and other branches.
export function colabNotebookUrl(config, pageUrl) {
  const page = new URL(pageUrl);
  let repository = config.githubRepository?.trim();
  if (!repository && /^[a-z0-9-]+\.github\.io$/i.test(page.hostname)) {
    const owner = page.hostname.split('.')[0];
    const project = page.pathname.split('/').filter(Boolean)[0];
    repository = `${owner}/${project && project !== 'index.html' ? project : `${owner}.github.io`}`;
  }
  if (!repository) return null;
  if (!/^[a-z0-9_.-]+\/[a-z0-9_.-]+$/i.test(repository)) throw Error('GitHub 저장소 설정을 확인해주세요.');
  const ref = config.githubRef || 'main';
  const path = config.notebookPath || 'colab/Pi3X_SPACE.ipynb';
  if (typeof ref !== 'string' || typeof path !== 'string' || !path.endsWith('.ipynb') ||
      path.split('/').some(part => !part || part === '..' || part === '.')) throw Error('노트북 경로 설정을 확인해주세요.');
  return `https://colab.research.google.com/github/${repository}/blob/${encodeURIComponent(ref)}/${path.split('/').map(encodeURIComponent).join('/')}`;
}

export function notebookCode(notebook, viewerUrl) {
  const cells = notebook.cells.filter(cell => cell.cell_type === 'code');
  if (!cells.length) throw Error('노트북에 실행 코드가 없어요.');
  return cells.map(cell => (Array.isArray(cell.source) ? cell.source.join('') : cell.source)
    .replace(/^VIEWER_URL = .*$/m, `VIEWER_URL = ${JSON.stringify(viewerUrl)}`))
    .join('\n\n');
}

function renderMarkdown(source) {
  const section = document.createElement('section'); section.className = 'notebook-markdown';
  // Render the notebook's small Markdown subset using text nodes only.
  for (const line of source.split('\n').filter(line => line.trim())) {
    const heading = line.match(/^(#{1,3})\s+(.*)/);
    const item = document.createElement(heading ? 'h3' : 'p');
    item.textContent = (heading ? heading[2] : line)
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/\*\*|`/g, '');
    section.append(item);
  }
  return section;
}

export function initNotebook(toast) {
  let notebookPromise;
  let combinedCode = '';
  const page = new URL(location.href);
  page.search = ''; page.hash = '';
  const viewerUrl = page.href;
  $('viewer-address').value = viewerUrl;

  async function copyText(value, fallback) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      if (fallback instanceof HTMLTextAreaElement) fallback.hidden = false;
      fallback.value = value; fallback.focus(); fallback.select();
      try { if (document.execCommand('copy')) return true; } catch { /* Leave selection available. */ }
      return false;
    }
  }
  $('viewer-address-copy').onclick = async () => {
    const copied = await copyText(viewerUrl, $('viewer-address'));
    toast(copied ? '웹 화면 주소를 복사했어요. VIEWER_URL에 넣어주세요.' : '주소가 선택됐어요. Ctrl+C 또는 ⌘C로 복사해주세요.');
  };

  const configReady = fetch(new URL('./space.config.json', import.meta.url))
    .then(response => { if (!response.ok) throw Error('설정을 불러오지 못했어요.'); return response.json(); })
    .then(config => {
      const url = colabNotebookUrl(config, location.href);
      if (!url) {
        $('notebook-open-hint').textContent = '로컬 미리보기에서는 노트북 보기 → 실행 코드 전체 복사 후 Colab의 새 코드 셀에 붙여넣으세요.';
        return;
      }
      for (const id of ['colab-open', 'notebook-colab-open']) $(id).href = url;
      $('notebook-open-hint').textContent = 'GitHub의 노트북을 Colab에서 바로 열어요. 다운로드는 필요 없어요.';
    })
    .catch(error => { $('notebook-open-hint').textContent = `${error.message} 페이지에서 노트북을 열고 실행 코드를 복사할 수 있어요.`; });

  async function loadNotebook() {
    await configReady;
    notebookPromise ??= fetch(new URL('./colab/Pi3X_SPACE.ipynb', import.meta.url))
      .then(response => { if (!response.ok) throw Error('노트북 파일을 불러오지 못했어요.'); return response.json(); });
    try {
      const notebook = await notebookPromise;
      combinedCode = notebookCode(notebook, viewerUrl);
      $('notebook-cells').replaceChildren();
      let codeIndex = 0;
      for (const cell of notebook.cells) {
        const source = Array.isArray(cell.source) ? cell.source.join('') : cell.source;
        if (cell.cell_type === 'code') {
          const details = document.createElement('details'); details.className = 'notebook-cell';
          const summary = document.createElement('summary'); summary.textContent = `코드 ${++codeIndex} · ${codeIndex === 1 ? 'GPU 확인과 준비' : 'Pi3X 서버 시작'}`;
          const pre = document.createElement('pre'); const code = document.createElement('code');
          code.textContent = source.replace(/^VIEWER_URL = .*$/m, `VIEWER_URL = ${JSON.stringify(viewerUrl)}`);
          pre.append(code); details.append(summary, pre); $('notebook-cells').append(details);
        } else if (cell.cell_type === 'markdown') {
          $('notebook-cells').append(renderMarkdown(source));
        }
      }
      $('notebook-copy').disabled = false;
      $('notebook-status').textContent = '코드 복사로 시작할 때는 Colab에서 새 노트북을 만들고 코드 셀 하나에 붙여넣으세요. 이 페이지의 복사 코드에는 돌아올 웹 주소가 이미 적용돼 있어요.';
    } catch (error) {
      notebookPromise = null;
      $('notebook-status').textContent = `${error.message} 창을 다시 열어 재시도해주세요.`;
    }
  }
  $('notebook-open').onclick = () => {
    $('connect-dialog').close(); $('notebook-dialog').showModal(); return loadNotebook();
  };
  $('notebook-back').onclick = () => { $('notebook-dialog').close(); $('connect-dialog').showModal(); };
  $('notebook-copy').onclick = async () => {
    const copied = await copyText(combinedCode, $('notebook-copy-source'));
    $('notebook-status').textContent = copied
      ? '복사했어요! Colab에서 새 노트북 → 코드 셀에 붙여넣기 → T4 GPU 선택 → 실행하세요.'
      : '아래 실행 코드가 선택됐어요. Ctrl+C 또는 ⌘C로 복사해주세요.';
    if (copied) { $('notebook-copy-source').hidden = true; toast('Colab 실행 코드를 복사했어요.'); }
  };
}
