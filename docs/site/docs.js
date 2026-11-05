const sidebar = document.querySelector('.sidebar');
const narrow = matchMedia('(max-width: 48rem)');
function syncSidebar() { sidebar.open = !narrow.matches; }
narrow.addEventListener('change', syncSidebar);
syncSidebar();

const search = document.getElementById('search');
const groups = sidebar.querySelectorAll('.sidebar-group');
const status = document.getElementById('search-status');
search.addEventListener('input', () => {
    const terms = search.value.toLowerCase().trim().split(/\s+/);
    let count = 0;
    groups.forEach(group => {
        let found = false;
        group.querySelectorAll('a').forEach(link => {
            const match = terms.every(term => link.textContent.toLowerCase().includes(term));
            link.hidden = !match;
            if (match) { found = true; count++; }
        });
        group.hidden = !found;
    });
    status.textContent = count ? '' : 'No matching documents.';
});
