// Config — placeholders replaced at container startup by entrypoint.sh
const SUPABASE_URL = '__SUPABASE_URL__';
const SUPABASE_ANON_KEY = '__SUPABASE_ANON_KEY__';

const sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Simple hash-based router
function getRoute() {
    const hash = window.location.hash || '#/';
    if (hash.startsWith('#/edition/')) {
        return { view: 'reader', edition: parseInt(hash.split('/')[2]) };
    }
    if (hash === '#/subscribe') {
        return { view: 'subscribe' };
    }
    return { view: 'list' };
}

function showView(viewName) {
    document.getElementById('list-view').style.display = viewName === 'list' ? 'block' : 'none';
    document.getElementById('reader-view').style.display = viewName === 'reader' ? 'block' : 'none';
    document.getElementById('subscribe-view').style.display = viewName === 'subscribe' ? 'block' : 'none';
}

// Load newsletter list
async function loadList() {
    showView('list');
    const { data, error } = await sb
        .from('newsletters')
        .select('edition_number, title, content_markdown, published_at')
        .eq('status', 'published')
        .order('edition_number', { ascending: false });

    if (error || !data || data.length === 0) {
        document.getElementById('newsletter-list').innerHTML = '<p>No newsletters published yet.</p>';
        return;
    }

    const html = data.map(function(n) {
        var date = new Date(n.published_at).toLocaleDateString('en-US', {
            year: 'numeric', month: 'long', day: 'numeric'
        });
        var excerpt = (n.content_markdown || '').replace(/[#*_\[\]]/g, '').substring(0, 150) + '...';

        return '<div class="edition-card">' +
            '<div class="edition-meta">Edition #' + n.edition_number + ' &middot; ' + date + '</div>' +
            '<a href="#/edition/' + n.edition_number + '" class="edition-title">' + n.title + '</a>' +
            '<p class="edition-excerpt">' + excerpt + '</p>' +
            '</div>';
    }).join('');

    document.getElementById('newsletter-list').innerHTML = html;
}

// Load single edition
async function loadEdition(editionNumber) {
    showView('reader');
    const { data, error } = await sb
        .from('newsletters')
        .select('*')
        .eq('edition_number', editionNumber)
        .eq('status', 'published')
        .single();

    if (error || !data) {
        document.getElementById('newsletter-content').innerHTML = '<p>Edition not found.</p>';
        return;
    }

    var date = new Date(data.published_at).toLocaleDateString('en-US', {
        year: 'numeric', month: 'long', day: 'numeric'
    });

    var rendered = marked.parse(data.content_markdown || '');

    document.getElementById('newsletter-content').innerHTML =
        '<h1>' + data.title + '</h1>' +
        '<div class="article-meta">Edition #' + data.edition_number + ' &middot; Published ' + date + '</div>' +
        rendered;

    window.scrollTo(0, 0);
}

// Router
function route() {
    var r = getRoute();
    switch (r.view) {
        case 'list': loadList(); break;
        case 'reader': loadEdition(r.edition); break;
        case 'subscribe': showView('subscribe'); break;
    }
}

// Subscribe form placeholder
document.addEventListener('DOMContentLoaded', function() {
    var form = document.getElementById('subscribe-form');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            form.innerHTML = '<p>Coming soon! Check back later.</p>';
        });
    }
});

window.addEventListener('hashchange', route);
window.addEventListener('DOMContentLoaded', route);
