// NOTE: Requires RLS policy on subscribers: CREATE POLICY "Allow public subscribe" ON subscribers FOR INSERT WITH CHECK (true);

// Config — placeholders replaced at container startup by entrypoint.sh
const SUPABASE_URL = '__SUPABASE_URL__';
const SUPABASE_ANON_KEY = '__SUPABASE_ANON_KEY__';

const sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// ─── Mode State ──────────────────────────────────────────────────────────────

const MODES = {
    builder: {
        stylesheet: '/style-builder.css',
        contentField: 'content_markdown',
        titleField: 'title',
        label: 'Builder',
        icon: '\u26A1'
    },
    impact: {
        stylesheet: '/style-impact.css',
        contentField: 'content_markdown_impact',
        titleField: 'title_impact',
        label: 'Impact',
        icon: '\uD83C\uDF0D'
    }
};

// Resolve initial mode: URL param > localStorage > default 'impact'
function getInitialMode() {
    var urlMode = new URL(window.location).searchParams.get('mode');
    if (urlMode && MODES[urlMode]) return urlMode;
    var stored = localStorage.getItem('agentpulse_mode');
    if (stored && MODES[stored]) return stored;
    return 'impact';
}

var currentMode = getInitialMode();

function setMode(mode) {
    if (!MODES[mode]) return;
    currentMode = mode;
    localStorage.setItem('agentpulse_mode', mode);

    // Update URL param without reload
    var url = new URL(window.location);
    url.searchParams.set('mode', mode);
    history.replaceState({}, '', url);

    // Swap stylesheet
    document.getElementById('mode-stylesheet').href = MODES[mode].stylesheet;

    // Update body class
    document.body.classList.remove('builder', 'impact');
    document.body.classList.add(mode);

    // Update toggle UI
    var track = document.querySelector('.toggle-track');
    track.classList.remove('builder', 'impact');
    track.classList.add(mode);

    // Update toggle label highlights
    var builderLbl = document.querySelector('.builder-lbl');
    var impactLbl = document.querySelector('.impact-lbl');
    if (builderLbl) builderLbl.classList.toggle('active', mode === 'builder');
    if (impactLbl) impactLbl.classList.toggle('active', mode === 'impact');

    // Add transition class
    document.body.classList.add('mode-transitioning');
    setTimeout(function() {
        document.body.classList.remove('mode-transitioning');
    }, 400);

    // Flash mode indicator
    flashIndicator(mode);

    // Re-render current article if loaded (without refetching)
    if (window.currentNewsletter) {
        renderArticle(window.currentNewsletter);
    }

    // Re-render list if visible
    if (window.currentNewsletterList && document.getElementById('list-view').style.display !== 'none') {
        renderList(window.currentNewsletterList);
    }
}

function toggleMode() {
    setMode(currentMode === 'builder' ? 'impact' : 'builder');
}

function flashIndicator(mode) {
    var el = document.getElementById('mode-indicator');
    if (!el) return;
    el.textContent = MODES[mode].icon + ' ' + MODES[mode].label + ' Mode';
    el.classList.add('flash');
    setTimeout(function() {
        el.classList.remove('flash');
    }, 1500);
}

// ─── Router ──────────────────────────────────────────────────────────────────

function getRoute() {
    var hash = window.location.hash || '#/';
    if (hash.startsWith('#/edition/')) {
        return { view: 'reader', edition: parseInt(hash.split('/')[2]) };
    }
    if (hash.startsWith('#/unsubscribe')) {
        return { view: 'unsubscribe' };
    }
    return { view: 'list' };
}

function showView(viewName) {
    document.getElementById('list-view').style.display = viewName === 'list' ? 'block' : 'none';
    document.getElementById('reader-view').style.display = viewName === 'reader' ? 'block' : 'none';
}

// ─── List View ───────────────────────────────────────────────────────────────

function renderList(data) {
    var html = data.map(function(n) {
        var date = new Date(n.published_at).toLocaleDateString('en-US', {
            year: 'numeric', month: 'long', day: 'numeric'
        });

        // Use mode-appropriate title (fall back to default title)
        var title = (currentMode === 'impact' && n.title_impact) ? n.title_impact : n.title;

        // Use mode-appropriate content for excerpt
        var content = (currentMode === 'impact' && n.content_markdown_impact)
            ? n.content_markdown_impact
            : (n.content_markdown || '');
        var excerpt = content.replace(/[#*_\[\]]/g, '').substring(0, 150) + '...';

        return '<div class="edition-card">' +
            '<div class="edition-meta">Edition #' + n.edition_number + ' &middot; ' + date + '</div>' +
            '<a href="#/edition/' + n.edition_number + '" class="edition-title">' + escapeHtml(title) + '</a>' +
            '<p class="edition-excerpt">' + escapeHtml(excerpt) + '</p>' +
            '</div>';
    }).join('');

    document.getElementById('newsletter-list').innerHTML = html;
}

async function loadList() {
    showView('list');
    var { data, error } = await sb
        .from('newsletters')
        .select('*')
        .eq('status', 'published')
        .order('edition_number', { ascending: false });

    if (error || !data || data.length === 0) {
        document.getElementById('newsletter-list').innerHTML = '<p>No newsletters published yet.</p>';
        return;
    }

    window.currentNewsletterList = data;
    renderList(data);
}

// ─── Reader View ─────────────────────────────────────────────────────────────

function renderArticle(data) {
    // Pick mode-appropriate content (fall back to builder version)
    var title = (currentMode === 'impact' && data.title_impact) ? data.title_impact : data.title;
    var content = (currentMode === 'impact' && data.content_markdown_impact)
        ? data.content_markdown_impact
        : (data.content_markdown || '');

    var date = new Date(data.published_at).toLocaleDateString('en-US', {
        year: 'numeric', month: 'long', day: 'numeric'
    });

    var rendered = marked.parse(content);

    document.getElementById('newsletter-content').innerHTML =
        '<h1>' + escapeHtml(title) + '</h1>' +
        '<div class="article-meta">Edition #' + data.edition_number + ' &middot; Published ' + date + '</div>' +
        rendered;
}

async function loadEdition(editionNumber) {
    showView('reader');

    var { data, error } = await sb
        .from('newsletters')
        .select('*')
        .eq('edition_number', editionNumber)
        .eq('status', 'published')
        .single();

    if (error || !data) {
        document.getElementById('newsletter-content').innerHTML = '<p>Edition not found.</p>';
        return;
    }

    // Store for mode-toggle re-render without refetching
    window.currentNewsletter = data;
    renderArticle(data);
    window.scrollTo(0, 0);
}

// ─── Subscribe Handler ──────────────────────────────────────────────────────

async function handleSubscribe() {
    var email = document.getElementById('subscribe-email').value.trim();
    var pref = document.querySelector('input[name="pref"]:checked');
    var status = document.getElementById('subscribe-status');
    var btn = document.getElementById('subscribe-btn');

    if (!email || !email.includes('@')) {
        status.textContent = 'Please enter a valid email.';
        status.style.color = 'var(--color-accent)';
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Subscribing...';

    try {
        var newPref = pref ? pref.value : 'impact';
        var { data, error } = await sb
            .from('subscribers')
            .upsert({
                email: email,
                mode_preference: newPref,
                status: 'active',
                unsubscribed_at: null
            }, { onConflict: 'email' })
            .select('mode_preference');

        if (error) {
            throw error;
        } else {
            status.textContent = "You're in! You'll receive the next edition.";
            status.style.color = 'var(--color-accent)';
            document.getElementById('subscribe-email').value = '';
        }
    } catch (err) {
        console.error('Subscribe error:', err);
        status.textContent = 'Something went wrong. Try again.';
        status.style.color = 'var(--color-accent)';
    }

    btn.disabled = false;
    btn.textContent = 'Subscribe';
}

// ─── Utility ─────────────────────────────────────────────────────────────────

function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

// ─── Init ────────────────────────────────────────────────────────────────────

// ─── Unsubscribe Handler ────────────────────────────────────────────────────

async function handleUnsubscribe() {
    showView('reader');
    var container = document.getElementById('newsletter-content');

    // Parse subscriber ID from hash: #/unsubscribe?id=xxx
    var id = null;
    var hashParts = (window.location.hash || '').split('?');
    if (hashParts[1]) {
        var hashParams = new URLSearchParams(hashParts[1]);
        id = hashParams.get('id');
    }

    if (!id) {
        container.innerHTML = '<h2>Invalid unsubscribe link</h2><p>No subscriber ID found.</p>';
        return;
    }

    try {
        var { error } = await sb.rpc('unsubscribe', { subscriber_id: id });
        if (error) throw error;
        container.innerHTML = '<h2>Unsubscribed</h2>' +
            '<p>You have been removed from the AgentPulse mailing list.</p>' +
            '<p>You can re-subscribe anytime from the <a href="#/">homepage</a>.</p>';
    } catch (err) {
        console.error('Unsubscribe error:', err);
        container.innerHTML = '<h2>Unsubscribe failed</h2><p>Something went wrong. Please try again.</p>';
    }
}

function route() {
    window.currentNewsletter = null;
    var r = getRoute();
    switch (r.view) {
        case 'list': loadList(); break;
        case 'reader': loadEdition(r.edition); break;
        case 'unsubscribe': handleUnsubscribe(); break;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Apply initial mode (sets body class, stylesheet, toggle UI, URL)
    setMode(currentMode);
    route();
});

window.addEventListener('hashchange', route);
