import {
    formatBytes,
    formatBytesWithOrig,
    formatKeyToLabel,
    fetchPage,
    downloadFile,
    viewFile,
    prettyPrint,
    loadCSS,
    moveNode,
    viewSnapshotDetail,
    submitFilter,
    fetchDashboardStats,
    fetchConfigKeys,
    fetchCacheStats,
    fetchCacheClear,
} from './utils.js';

// Alpine.js is included via CDN, so this file can be empty or include custom scripts
document.addEventListener('alpine:init', () => {
    // Custom Alpine.js components can be added here if needed
    Alpine.store('_d', {
        time: null,
        url: null,
        snapshot_data: {'summary': []},
        open_snapshot_modal: false,
    });

    Alpine.store('utils', {
        formatBytes: formatBytes,
        formatBytesWithOrig: formatBytesWithOrig,
        formatKeyToLabel: formatKeyToLabel,
        fetchPage: fetchPage,
        downloadFile: downloadFile,
        viewFile: viewFile,
        prettyPrint: prettyPrint,
        viewSnapshotDetail: viewSnapshotDetail,
        submitFilter: submitFilter,
        fetchDashboardStats: fetchDashboardStats,
        fetchConfigKeys: fetchConfigKeys,
        fetchCacheStats: fetchCacheStats,
        fetchCacheClear: fetchCacheClear,
    });

    Alpine.store('notification', {
        init() {
            console.debug("notification.init")
        },
        on: false,
        html: '',
        open() {
            this.on = true
        },
        close() {
            this.on = false
        },
    });

    Alpine.store('modal', {
        init() {
            console.debug("modal.init")
        },
        on: false,
        html: '',
        open() {
            this.on = true
        },
        close() {
            this.on = false
        },
    });

    Alpine.store('pagination', {
        url: '',
        page: 1,
        total_pages: null, 
        record_count: null, 
        loading: false,

        init() {
            console.debug("pagination.init")
        },
        next() {
            const $data = this;
            $data.loading = true;
            let {url, page, total_pages} = $data;
            let new_page = (page + 1);
            if (new_page > total_pages) {
                new_page = total_pages;
            }
            this.fetch(url, new_page).then(() => {
                $data.page = new_page;
                $data.loading = false;
            });
        },
        previous() {
            const $data = this;
            $data.loading = true;
            let {url, page} = $data;
            let new_page = (page - 1);
            if (new_page < 1) {
                new_page = 1;
            }
            this.fetch(url, new_page).then(() => {
                $data.page = new_page;
                $data.loading = false;
            });
        },
        first() {
            const $data = this;
            $data.loading = true;
            let {url} = $data;
            let new_page = 1;
            this.fetch(url, new_page).then(() => {
                $data.page = new_page;
                $data.loading = false;
            });
        },
        last() {
            const $data = this;
            $data.loading = true;
            let {url, total_pages} = $data;
            let new_page = total_pages;
            this.fetch(url, new_page).then(() => {
                $data.page = new_page;
                $data.loading = false;
            });
        },
        fetch(url, new_page) {
            const $utils = Alpine.store('utils')
            const sep = url.includes('?') ? '&' : '?';
            const new_url = `${url}${sep}is_ajax=1&page=${new_page}`
            return $utils.fetchPage(new_url, "#records_block")
        }
    });

    /*
    Alpine.data('footer', () => ({
        time: null,
        init() {
            Alpine.effect(() => {
                this.time = Alpine.store('_d').time;
            })
        },
        destroy() {
            
        },
    }));
    */
});


document.addEventListener('DOMContentLoaded', function() {
    // Move snapshot detail template from snapshot list page
    moveNode('snapshot_list_summary', 'modal_div');
});
