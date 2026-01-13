// Client logic: previews, drag & drop reorder, submission building (keeps order),
// server-side listing and thumbnails, and download handling.

document.addEventListener('DOMContentLoaded', function(){
  const modeRadios = document.querySelectorAll('input[name="mode"]');
  const uploadSection = document.getElementById('uploadSection');
  const serverSection = document.getElementById('serverSection');
  const listBtn = document.getElementById('listBtn');
  const serverList = document.getElementById('serverList');
  const folderInput = document.getElementById('folder');
  const saveOption = document.getElementById('saveOption');
  const saveFolderRow = document.getElementById('saveFolderRow');
  const form = document.getElementById('concatForm');
  const result = document.getElementById('result');
  const imagesInput = document.getElementById('images');
  const uploadPreview = document.getElementById('uploadPreview');
  const orientationSelect = document.getElementById('orientation');
  const alignmentSelect = document.getElementById('alignment');
  const resizeMode = document.getElementById('resize_mode');
  const fitInputs = document.getElementById('fitInputs');

  let uploadFiles = []; // Array of File objects in current preview order
  let serverSelection = []; // Array of {name, thumbUrl} objects in order

  function toggleModeSections(){
    const mode = document.querySelector('input[name="mode"]:checked').value;
    if (mode === 'upload') {
      uploadSection.style.display = '';
      serverSection.style.display = 'none';
    } else {
      uploadSection.style.display = 'none';
      serverSection.style.display = '';
    }
  }

  modeRadios.forEach(r => r.addEventListener('change', toggleModeSections));
  toggleModeSections();

  saveOption.addEventListener('change', function(){
    saveFolderRow.style.display = this.value === 'save' ? '' : 'none';
  });

  resizeMode.addEventListener('change', function(){
    fitInputs.style.display = this.value === 'fit_max' ? '' : 'none';
  });

  // Utility to create draggable thumbnail nodes
  function createThumbNode({id, title, imgSrc, isFile=true, fileRef=null}) {
    const item = document.createElement('div');
    item.className = 'thumb-item';
    item.draggable = true;
    item.dataset.id = id;
    item.innerHTML = `
      <div class="thumb-inner">
        <img class="thumb-img" src="${imgSrc}" alt="${title}" />
        <div class="thumb-caption">${title}</div>
      </div>
    `;
    // store reference to file if provided
    if (isFile && fileRef) item._file = fileRef;
    // drag handlers
    item.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', id);
      item.classList.add('dragging');
    });
    item.addEventListener('dragend', () => {
      item.classList.remove('dragging');
    });
    item.addEventListener('dragover', (e) => {
      e.preventDefault();
      item.classList.add('drag-over');
    });
    item.addEventListener('dragleave', () => {
      item.classList.remove('drag-over');
    });
    item.addEventListener('drop', (e) => {
      e.preventDefault();
      const draggedId = e.dataTransfer.getData('text/plain');
      if (!draggedId) return;
      const dragged = item.parentNode.querySelector(`[data-id="${draggedId}"]`);
      if (!dragged) return;
      // insert dragged before this item (swap)
      if (dragged === item) return;
      item.parentNode.insertBefore(dragged, item);
      // cleanup classes
      item.classList.remove('drag-over');
      updateUploadFilesFromPreview();
    });
    return item;
  }

  // When user selects files via input, create previews and store File references
  imagesInput.addEventListener('change', function(){
    uploadFiles = Array.from(this.files || []);
    renderUploadPreview();
  });

  function renderUploadPreview(){
    uploadPreview.innerHTML = '';
    uploadFiles.forEach((file, idx) => {
      const id = 'u_' + idx + '_' + encodeURIComponent(file.name);
      const reader = new FileReader();
      reader.onload = function(e){
        const node = createThumbNode({id, title: file.name, imgSrc: e.target.result, isFile:true, fileRef:file});
        uploadPreview.appendChild(node);
      };
      reader.readAsDataURL(file);
    });
  }

  function updateUploadFilesFromPreview(){
    // Rebuild uploadFiles array from preview DOM order
    const nodes = Array.from(uploadPreview.querySelectorAll('.thumb-item'));
    uploadFiles = nodes.map(n => n._file).filter(Boolean);
  }

  // Server folder listing
  listBtn.addEventListener('click', function(){
    serverList.innerHTML = 'Loading...';
    fetch('/list_folder', {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: new URLSearchParams({folder: folderInput.value})
    }).then(r => r.json())
      .then(j => {
        if (!j.ok) {
          serverList.innerHTML = '<div class="error">' + (j.error || 'Error') + '</div>';
          return;
        }
        if (!j.images.length) {
          serverList.innerHTML = '<div class="hint">No images found in folder.</div>';
          return;
        }
        serverSelection = [];
        serverList.innerHTML = '';
        j.images.forEach((name, idx) => {
          const id = 's_' + idx + '_' + encodeURIComponent(name);
          const thumbUrl = `/thumbnail/${encodeURIComponent(folderInput.value)}/${encodeURIComponent(name)}`;
          const node = createThumbNode({id, title: name, imgSrc: thumbUrl, isFile:false});
          // toggle selection by click
          node.addEventListener('click', (e) => {
            node.classList.toggle('selected');
            rebuildServerSelectionFromDOM();
          });
          serverList.appendChild(node);
        });
        // instruct user to click items to select
        const hint = document.createElement('div');
        hint.className = 'hint';
        hint.textContent = 'Click items to toggle selection; drag selected items to reorder.';
        serverList.appendChild(hint);
      }).catch(err => {
        serverList.innerHTML = '<div class="error">Network error</div>';
      });
  });

  function rebuildServerSelectionFromDOM(){
    // selected nodes in DOM define serverSelection in that order
    const selected = Array.from(serverList.querySelectorAll('.thumb-item.selected'));
    serverSelection = selected.map(node => ({name: node.querySelector('.thumb-caption').textContent}));
  }

  // Build FormData with fields and either files (ordered) or selected[] (ordered),
  // send to /concatenate. If response is JSON (saved on server) display message,
  // otherwise treat as image blob and force download.
  form.addEventListener('submit', function(e){
    e.preventDefault();
    result.innerHTML = '';
    const fd = new FormData();
    const mode = document.querySelector('input[name="mode"]:checked').value;
    fd.append('mode', mode);
    fd.append('orientation', document.getElementById('orientation').value);
    fd.append('alignment', document.getElementById('alignment').value);
    fd.append('resize_mode', document.getElementById('resize_mode').value);
    const maxW = document.getElementById('max_width').value;
    const maxH = document.getElementById('max_height').value;
    if (maxW) fd.append('max_width', maxW);
    if (maxH) fd.append('max_height', maxH);
    fd.append('output_name', document.getElementById('output_name').value || 'output.png');
    fd.append('save_option', document.getElementById('saveOption').value);
    if (document.getElementById('saveOption').value === 'save') {
      fd.append('save_folder', document.getElementById('save_folder').value || 'outputs');
    }

    if (mode === 'upload') {
      // append upload files in preview order
      updateUploadFilesFromPreview();
      if (!uploadFiles.length) {
        result.innerHTML = '<div class="error">No files to upload.</div>';
        return;
      }
      uploadFiles.forEach(file => fd.append('images', file, file.name));
    } else {
      // server mode: we need folder + selected[] in order
      fd.append('folder', folderInput.value);
      // rebuild selection from DOM to preserve order
      rebuildServerSelectionFromDOM();
      if (!serverSelection.length) {
        result.innerHTML = '<div class="error">No server-side images selected.</div>';
        return;
      }
      serverSelection.forEach(item => fd.append('selected[]', item.name));
    }

    // send request
    fetch('/concatenate', {method: 'POST', body: fd})
      .then(async resp => {
        const contentType = resp.headers.get('Content-Type') || '';
        if (contentType.includes('application/json')) {
          const j = await resp.json();
          if (!j.ok) {
            result.innerHTML = '<div class="error">' + (j.error || 'Error') + '</div>';
            return;
          }
          if (j.saved) {
            result.innerHTML = `<div class="success">Saved on server: ${j.path}</div>`;
          } else {
            result.innerHTML = `<div class="success">Done.</div>`;
          }
          return;
        }
        // treat as file blob
        const blob = await resp.blob();
        // determine filename from content-disposition or output_name field
        let filename = document.getElementById('output_name').value || 'output.png';
        // create link to download
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      })
      .catch(err => {
        result.innerHTML = '<div class="error">Network error</div>';
      });
  });
});