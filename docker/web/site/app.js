// NOTE: Requires RLS policy on subscribers: CREATE POLICY "Allow public subscribe" ON subscribers FOR INSERT WITH CHECK (true);

// Config — placeholders replaced at container startup by entrypoint.sh
const SUPABASE_URL = '__SUPABASE_URL__';
const SUPABASE_ANON_KEY = '__SUPABASE_ANON_KEY__';

const sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// ─── Mode State ──────────────────────────────────────────────────────────────

const MODES = {
    technical: {
        contentField: 'content_markdown',
        titleField: 'title',
        label: 'Technical',
        subtitle: 'Architecture, code, implementation',
        dbPref: 'builder'
    },
    strategic: {
        contentField: 'content_markdown_impact',
        titleField: 'title_impact',
        label: 'Strategic',
        subtitle: 'Markets, strategy, implications',
        dbPref: 'impact'
    }
};

// ─── Economy-Map Constants (Phase 4) ──────────────────────────────────────────

// Editorial: edit this string + PR + redeploy to update (D-12). Wave 2 plan 02
// may revise. Keep under 200 chars; tone matches PROJECT.md core value.
const HUB_STORYLINE = 'Synthesis with editorial integrity. Eight blocks, seven shipped, one deferred — the agent economy as a living map.';

// Editorial: hardcoded #/status header (specifics §"Editorial copy"). PR + redeploy.
const STATUS_PAGE_HEADER = 'Maturity Snapshot';

// blocks.maturity enum → 1..5 stage for the maturity pill data-stage attribute.
const MATURITY_STAGE = { nascent: 1, emerging: 2, contested: 3, consolidating: 4, mature: 5 };

// Tier headings for the hub + status tier grouping (D-13). Hardcoded uppercase.
const TIER_LABELS = { substrate: 'SUBSTRATE', behavior: 'BEHAVIOR', frame: 'FRAME' };

// Exact-string-match contract (Phase 2 D-21 seed). Wave 2 plan 03 hides the
// tension card when blocks.live_tension === this value. Em-dash MUST match the
// seed exactly — do not substitute a hyphen.
const LIVE_TENSION_PLACEHOLDER = 'TBD — set via /map-tension';

// Resolve initial mode: URL param > localStorage > default 'technical'
function getInitialMode() {
    var urlMode = new URL(window.location).searchParams.get('mode');
    if (urlMode && MODES[urlMode]) return urlMode;
    // Migrate old localStorage values
    var stored = localStorage.getItem('agentpulse_mode');
    if (stored === 'builder') return 'technical';
    if (stored === 'impact') return 'strategic';
    if (stored && MODES[stored]) return stored;
    return 'technical';
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

    // Body class (drives CSS variables)
    document.body.classList.remove('technical', 'strategic');
    document.body.classList.add(mode);

    // Toggle buttons
    document.getElementById('btn-technical').classList.toggle('active', mode === 'technical');
    document.getElementById('btn-strategic').classList.toggle('active', mode === 'strategic');

    // Mode subtitle
    document.getElementById('mode-subtitle').textContent = MODES[mode].subtitle;

    // Transition
    document.body.classList.add('mode-transitioning');
    setTimeout(function() {
        document.body.classList.remove('mode-transitioning');
    }, 400);

    // Re-render current article if loaded (without refetching)
    if (window.currentNewsletter) {
        renderArticle(window.currentNewsletter);
    }

    // Re-render list if visible
    if (window.currentNewsletterList && document.getElementById('list-view').style.display !== 'none') {
        renderList(window.currentNewsletterList);
    }
}

// ─── Hero ────────────────────────────────────────────────────────────────────

function updateHero(title, dateText) {
    document.getElementById('hero-headline').textContent = title || '';
    document.getElementById('hero-date').textContent = dateText || '';
}

// ─── Router ──────────────────────────────────────────────────────────────────

function getRoute() {
    var hash = window.location.hash || '#/';
    if (hash.startsWith('#/map/')) {
        return { view: 'block', slug: hash.split('/')[2] };
    }
    if (hash.startsWith('#/map')) {
        return { view: 'map' };
    }
    if (hash.startsWith('#/status')) {
        return { view: 'status' };
    }
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
    document.getElementById('map-view').style.display = viewName === 'map' ? 'block' : 'none';
    document.getElementById('block-view').style.display = viewName === 'block' ? 'block' : 'none';
    document.getElementById('status-view').style.display = viewName === 'status' ? 'block' : 'none';

    // Hide the technical/strategic mode toggle on map routes (D-03). The body
    // class stays so the --accent-tier cascade still resolves; only the toggle
    // UI and its subtitle are hidden. Defensive null-checks per PATTERNS §3.
    var isMapRoute = (viewName === 'map' || viewName === 'block' || viewName === 'status');
    var toggle = document.querySelector('.mode-toggle');
    if (toggle) toggle.style.display = isMapRoute ? 'none' : 'inline-flex';
    var subtitle = document.getElementById('mode-subtitle');
    if (subtitle) subtitle.style.display = isMapRoute ? 'none' : 'block';
}

// ─── List View ───────────────────────────────────────────────────────────────

function renderList(data) {
    if (!data || data.length === 0) {
        document.getElementById('newsletter-list').innerHTML =
            '<div class="content-area"><p style="color:var(--text-secondary);font-size:15px;">No newsletters published yet.</p></div>';
        updateHero('AI Agents Pulse', '');
        return;
    }

    // Update hero with site title and latest edition date
    var latest = data[0];
    var latestDate = formatDate(latest.published_at);
    updateHero('AI Agents Pulse', 'Latest: Edition #' + latest.edition_number + ' \u00b7 ' + latestDate);

    var html = data.map(function(n) {
        var title = getModeTitle(n);
        var content = getModeContent(n);
        var excerpt = content.replace(/[#*_\[\]`>]/g, '').substring(0, 150) + '...';

        return '<div class="article-entry">' +
            '<div class="section-label">EDITION #' + n.edition_number + '</div>' +
            '<a href="#/edition/' + n.edition_number + '" class="entry-title">' + escapeHtml(title) + '</a>' +
            '<p class="entry-preview">' + escapeHtml(excerpt) + '</p>' +
            '</div>';
    }).join('');

    document.getElementById('newsletter-list').innerHTML = html;
}

async function loadList() {
    showView('list');
    var { data, error } = await sb
        .from('newsletters')
        .select('*')
        .in('status', ['published', 'preview'])
        .order('edition_number', { ascending: false });

    if (error || !data || data.length === 0) {
        document.getElementById('newsletter-list').innerHTML =
            '<p style="color:var(--text-secondary);font-size:15px;padding:20px 24px;">No newsletters published yet.</p>';
        updateHero('AI Agents Pulse', '');
        return;
    }

    window.currentNewsletterList = data;
    renderList(data);
}

// ─── Reader View ─────────────────────────────────────────────────────────────

function renderArticle(data) {
    var title = getModeTitle(data);
    var content = getModeContent(data);
    var date = formatDate(data.published_at || data.created_at);

    // Update hero with edition info
    updateHero(title, 'Edition #' + data.edition_number + ' \u00b7 ' + date);

    var banner = '';
    if (data.status === 'preview') {
        banner = '<div style="background:#f59e0b;color:#000;padding:10px 16px;border-radius:6px;margin-bottom:16px;font-weight:600;text-align:center;">PREVIEW — NOT YET PUBLISHED</div>';
    }

    var rendered = marked.parse(content);
    document.getElementById('newsletter-content').innerHTML = banner + rendered;
}

async function loadEdition(editionNumber) {
    showView('reader');

    var { data, error } = await sb
        .from('newsletters')
        .select('*')
        .eq('edition_number', editionNumber)
        .in('status', ['published', 'preview'])
        .single();

    if (error || !data) {
        document.getElementById('newsletter-content').innerHTML =
            '<p style="color:var(--text-secondary);">Edition not found.</p>';
        updateHero('Edition Not Found', '');
        return;
    }

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
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Subscribing...';

    try {
        // Map frontend mode names to backend values for backward compat
        var prefValue = pref ? pref.value : 'technical';
        var dbMode = prefValue === 'technical' ? 'builder'
                   : prefValue === 'strategic' ? 'impact'
                   : 'both';

        var { error } = await sb.rpc('subscribe', {
            p_email: email,
            p_mode: dbMode
        });

        if (error) throw error;

        status.textContent = "You're in! You'll receive the next edition.";
        document.getElementById('subscribe-email').value = '';
    } catch (err) {
        console.error('Subscribe error:', err);
        status.textContent = 'Something went wrong. Try again.';
    }

    btn.disabled = false;
    btn.textContent = 'Subscribe';
}

function scrollToSubscribe() {
    document.getElementById('subscribe-section').scrollIntoView({ behavior: 'smooth' });
}

// ─── Unsubscribe Handler ────────────────────────────────────────────────────

async function handleUnsubscribe() {
    showView('reader');
    var container = document.getElementById('newsletter-content');
    updateHero('Unsubscribe', '');

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

// ─── Utility ─────────────────────────────────────────────────────────────────

function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

function formatDate(isoStr) {
    if (!isoStr) return '';
    return new Date(isoStr).toLocaleDateString('en-US', {
        year: 'numeric', month: 'long', day: 'numeric'
    });
}

function getModeTitle(data) {
    if (currentMode === 'strategic' && data.title_impact) return data.title_impact;
    return data.title;
}

function getModeContent(data) {
    if (currentMode === 'strategic' && data.content_markdown_impact) return data.content_markdown_impact;
    return data.content_markdown || '';
}

// ─── Map Loaders (Phase 4 — stubs; renderers ship in Wave 2) ──────────────────

// Stub loaders so route() resolves without ReferenceError. Each flips view
// visibility via showView() so the shell works before the Wave 2 renderers
// plug in the data + markup.
async function loadHub() {
    showView('map');
    /* renderer in Wave 2 plan 02 */
}

async function loadBlock(slug) {
    showView('block');
    /* renderer in Wave 2 plan 03 */
}

async function loadStatus() {
    showView('status');
    /* renderer in Wave 2 plan 04 */
}

// ─── Init ────────────────────────────────────────────────────────────────────

function route() {
    window.currentNewsletter = null;
    var r = getRoute();
    switch (r.view) {
        case 'list': loadList(); break;
        case 'reader': loadEdition(r.edition); break;
        case 'unsubscribe': handleUnsubscribe(); break;
        case 'map': loadHub(); break;
        case 'block': loadBlock(r.slug); break;
        case 'status': loadStatus(); break;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    setMode(currentMode);
    route();
});

window.addEventListener('hashchange', route);
