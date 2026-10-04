
export function formatBytes (bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

export function formatBytesWithOrig (bytes, decimals = 2) {
    return formatBytes(bytes, decimals) + 
    `<span class='inline-flex items-center rounded-md bg-gray-100 px-1.5 py-0.5 text-xs font-medium text-gray-600'>
        ${bytes} bytes
    </span>`
}

export function formatKeyToLabel (str) {
    return str
    .split('_') // Split by underscores
    .map(word => word.charAt(0).toUpperCase() + word.slice(1)) // Capitalize each word
    .join(' '); // Join with spaces
}

export function fetchPage(_url, _selector="main") {
    // $model = Alpine.store('modal')
    // $model.open()
    const promise = fetch(
    _url, {
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XmlHttpRequest'
        },
    })
    .then(res => res.text())
    .then(text => {
        document.querySelector(_selector).innerHTML = text
    })
    .catch(error => {
        console.error('fetch page error:', error);
        alert('fetch page error');
    })
    // .finally(() => $dispatch('notify'))
    return promise;
}

export function downloadFile($data) {
    $data.loading = true;
    
    fetch($data.url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        file_path: $data.file_path,
        snapshot_id: $data.snapshot_id,
      })
    })
    .then(response => {
        // console.log(response.ok)
        if (!response.ok) throw new Error('Download failed');
        // Extract filename from headers before moving to blob()
        const contentDisposition = response.headers.get('content-disposition');
        const filename = contentDisposition 
            ? contentDisposition.split('filename=')[1].replace(/"/g, '')
            : 'download.file';

      return response.blob().then(blob => ({ blob, filename }));
    })
    .then(({blob, filename}) => {
        // Create a temporary URL for the blob
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
              
        // Clean up
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    })
    .catch(error => {
        console.error('Download error:', error.message);
        const $modal = Alpine.store('modal');
        $modal.html = `Download error: ${error.message}`;
        $modal.open();
    })
    .finally(() => {
      $data.loading = false;
    });
}

export function viewFile($data) {
    $data.loading = true;
    fetch($data.url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        // Add any other headers needed (like auth tokens)
      },
    })
    .then(async response => {
        if (!response.ok) {
            // Try to parse error body, fallback to empty object
            const errorData = await response.json().catch(() => ({}));
            const $notification = Alpine.store('notification');
            $notification.html = errorData.error || response.statusText;
            $notification.open();
            throw new Error(`HTTP ${response.status}: ${errorData.error || response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        const file_name = data.file_name
        const file_path = data.file_path
        const file_data = data.file_data
        const $modal = Alpine.store('modal');
        let $hgh_worker = null;
        if ( ! Alpine.store('highlight_worker')) {
            $hgh_worker =  new Worker("/static/js/highlight-worker.js")
            Alpine.store('highlight_worker', $hgh_worker);
            $hgh_worker.onmessage = (event) => {
                // console.log(event.data);
                $modal.html = "<pre><code class='hljs'>"+event.data+"</code></pre>";
                // console.log($modal.html);
            };
        } else {
            // Get the worker and send data
            $hgh_worker = Alpine.store('highlight_worker');
        }
        // console.log($hgh_worker);
        $hgh_worker.postMessage(file_data);
        loadCSS('/static/css/atom-one-dark.min.css');
    })
    .catch(error => {
        console.error('View file error:', error.message);
        // alert('Viewing file failed');
        const $modal = Alpine.store('modal');
        $modal.html = `View file error: ${error.message}`;
    })
    .finally(() => {
      const $modal = Alpine.store('modal');
      $modal.open();
      $data.loading = false;
    });
}

export function prettyPrint(obj, indent = 0) {
    const indentStr = '  '.repeat(indent);
    let result = '';

    if (typeof obj === 'object' && obj !== null) {
        if (Array.isArray(obj)) {
            result += `${indentStr}[\n`;
            obj.forEach(item => {
                result += prettyPrint(item, indent + 1) + '\n';
            });
            result += `${indentStr}]`;
        } else {
            result += `${indentStr}{\n`;
            for (const key in obj) {
                if (obj.hasOwnProperty(key)) {
                    result += `${indentStr}  ${key}: `;
                    // Handle the first line of the value
                    const valueStr = prettyPrint(obj[key], indent + 1);
                    // Split to handle multi-line values correctly
                    const lines = valueStr.split('\n');
                    result += lines[0];
                    // Add remaining lines with proper indentation
                    for (let i = 1; i < lines.length; i++) {
                        result += `\n${indentStr}  ${'  '.repeat(indent > 0 ? indent - 1 : 0)}${lines[i]}`;
                    }
                    result += '\n';
                }
            }
            result += `${indentStr}}`;
        }
    } else if (typeof obj === 'function') {
        result += `${obj.name || '(anonymous)'}()`;
    } else {
        result += `${indentStr}${obj}`;
    }

    return result;
}

export function loadCSS(path) {
    // Find all stylesheet links and check if any match the path
    const links = document.querySelectorAll('link[rel="stylesheet"]');
    const alreadyExists = Array.from(links).some(link => {
        // Extract just the path part (ignore domain and query strings)
        const linkPath = new URL(link.href, window.location.href).pathname;
        return linkPath === path;
    });

    if (!alreadyExists) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = path;
        document.head.appendChild(link);
    }
}

export function moveNode(source_id, target_id) {
    // Get the nodes
    const sourceNode = document.getElementById(source_id);
    const targetNode = document.getElementById(target_id);
    
    // Check if both nodes exist
    if (sourceNode && targetNode) {
        // Move the source node to the target node
        targetNode.appendChild(sourceNode);
    } else {
        // console.debug('One or both elements not found');
    }
}

export function viewSnapshotDetail(data) {
    Alpine.store('_d').snapshot_data = data;
    Alpine.store('_d').open_snapshot_modal = true;
    Alpine.store('modal').open();
}

export async function submitFilter(url) {
    const sep = url.includes('?') ? '&' : '?';
    const new_url = `${url}${sep}is_ajax=1&page=1&` + 
        new URLSearchParams(
            new FormData(document.getElementById('filter_form'))
        ).toString();
    await Alpine.store('utils').fetchPage(new_url, '#records_block')
}

export async function fetchDashboardStats($data) {
    $data.loading = true;
    $data.error = null;

    await fetch('/api/stats', {
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(async response => {
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const errorMsg = errorData.error_message || errorData.error || response.statusText || 'Failed to fetch repository statistics';
            throw new Error(errorMsg);
        }
        return response.json();
    })
    .then(data => {
        $data.stats = data;
    })
    .catch(error => {
        console.error('Fetch dashboard stats error:', error.message);
        $data.error = error.message;
        const $notification = Alpine.store('notification');
        if ($notification) {
            $notification.html = error.message;
            $notification.open();
        }
    })
    .finally(() => {
        $data.loading = false;
    });
}

// manage

export async function fetchConfigKeys($data) {
    if ($data.working) return;
    $data.result = {};
    $data.cache = {};
    $data.working = true;
    await fetch('/manage/config', {method: 'GET'})
        .then(res => {
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.json();
        })
        .then(data => $data.result = data)
        .catch(error => {
            console.error('Error:', error);
            $data.result = error;
        })
        .finally(() => $data.working = false);
}

export async function fetchCacheStats($data) {
    if ($data.working) return;
    $data.result = {};
    $data.cache = {};
    $data.working = true;
    await fetch('/manage/cache/stats', {method: 'GET'})
        .then(res => {
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.json();
        })
        .then(data => $data.cache = data)
        .catch(error => {
            console.error('Error:', error);
            $data.result = error;
        })
        .finally(() => $data.working = false);
}

export async function fetchCacheClear($data) {
    if ($data.working) return;
    $data.result = {};
    $data.cache = {};
    $data.working = true;
    fetch('/manage/cache/clear', {method: 'POST',})
        .then(res => {
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.json();
        })
        .then(data => $data.result = data)
        .catch(error => {
            console.error('Error:', error);
            $data.result = error;
        })
        .finally(() => $data.working = false);
}
