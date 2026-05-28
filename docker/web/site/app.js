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

// D-11: whether Show all was clicked; reset on each loadBlock() entry; read by the Wave 3 idle poll.
var timelineExpanded = false;

// Interval handle for the block-page Evolution refresh poll (D-05, D-06, D-07).
var evolutionPollHandle = null;

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

// Maturity pill — canonical tokens-preview.html markup (lines 78-82): ALWAYS
// exactly 5 seg children; CSS keys the fill off data-stage. MATURITY_STAGE
// resolves the enum; || 1 guards an unexpected value (renders as nascent).
// Module-scoped so renderHub() (plan 04-02) and renderBlock() (plan 04-03)
// share one definition — the only Phase-4-owned pill token site.
function renderMaturityPill(b) {
    var stage = MATURITY_STAGE[b.maturity] || 1;
    return '<div class="maturity-pill" data-accent="' + escapeHtml(b.accent) + '" data-stage="' + stage + '" aria-label="Maturity: ' + escapeHtml(b.maturity) + ' (' + stage + ' of 5)">' +
               '<span class="seg"></span><span class="seg"></span><span class="seg"></span><span class="seg"></span><span class="seg"></span>' +
           '</div>';
}

// ─── Map Loaders (Phase 4 — stubs; renderers ship in Wave 2) ──────────────────

// Stub loaders so route() resolves without ReferenceError. Each flips view
// visibility via showView() so the shell works before the Wave 2 renderers
// plug in the data + markup.
async function loadHub() {
    showView('map');

    // Single query — read all seven blocks ordered by sort_order. Per D-16 use
    // sb.schema('economy_map') so supabase-js sets Accept-Profile automatically.
    // Per D-17 NO defensive .eq('status', ...) filter — RLS is the boundary.
    var { data, error } = await sb
        .schema('economy_map')
        .from('blocks')
        .select('slug,title,subtitle,accent,tier,sort_order,maturity,live_tension,current_body_version_id,last_synthesized_at')
        .order('sort_order', { ascending: true });

    if (error || !data || data.length === 0) {
        console.error('loadHub error:', error);
        document.getElementById('map-view').querySelector('.content-area').innerHTML =
            '<p style="color:var(--text-secondary);font-size:15px;padding:20px 24px;">Map data unavailable.</p>';
        updateHero(HUB_STORYLINE, '');
        return;
    }

    window.currentBlocks = data;
    renderHub(data);
}

function renderHub(data) {
    // 1. Hero — use the latest last_synthesized_at across all blocks as the
    //    "updated" stamp (D-02). ISO string-sort works for ordering; omit the
    //    date entirely if every block has a null last_synthesized_at (v1 state).
    var latest = data.map(function(b) { return b.last_synthesized_at; }).filter(Boolean).sort().pop();
    var dateText = latest ? 'updated ' + formatDate(latest) : '';
    updateHero(HUB_STORYLINE, dateText);

    // 2. Group by tier. The query is already sort_order-ascending, so each
    //    filtered array preserves the seed order (Phase 2 D-23): substrate 1-3,
    //    behavior 4-6, frame 7.
    var substrateBlocks = data.filter(function(b) { return b.tier === 'substrate'; });
    var behaviorBlocks = data.filter(function(b) { return b.tier === 'behavior'; });
    var frameBlocks = data.filter(function(b) { return b.tier === 'frame'; });

    // 3. Single tile — whole <a> is the click target (D-14). encodeURIComponent
    //    on the slug is defense-in-depth; every DB string is escapeHtml'd.
    function renderTile(b) {
        return '<a href="#/map/' + encodeURIComponent(b.slug) + '" data-accent="' + escapeHtml(b.accent) + '" class="block-tile">' +
                   '<h3 class="tile-title">' + escapeHtml(b.title) + '</h3>' +
                   '<p class="tile-subtitle">' + escapeHtml(b.subtitle) + '</p>' +
                   renderMaturityPill(b) +
               '</a>';
    }

    // 4. Maturity pill is now a module-scoped helper (renderMaturityPill, defined
    //    near escapeHtml/formatDate) shared by renderHub + renderBlock (plan 04-03).

    // 5. Tier section wrapper — emits a <section class="tier-section"> with a
    //    <h2 class="tier-label"> heading followed by the joined tiles. Skips an
    //    empty array so no dangling heading appears (defensive; the seed always
    //    fills all three tiers).
    function tierSection(label, blocks) {
        if (!blocks.length) return '';
        return '<section class="tier-section">' +
                   '<h2 class="tier-label">' + label + '</h2>' +
                   blocks.map(renderTile).join('') +
               '</section>';
    }

    // 6. Storyline preface + three tier sections, written to the #map-view's
    //    .content-area container (provided by plan 04-01 Task 1).
    var html =
        '<div class="hub-storyline">' + escapeHtml(HUB_STORYLINE) + '</div>' +
        tierSection(TIER_LABELS.substrate, substrateBlocks) +
        tierSection(TIER_LABELS.behavior, behaviorBlocks) +
        tierSection(TIER_LABELS.frame, frameBlocks);

    document.getElementById('map-view').querySelector('.content-area').innerHTML = html;
    window.scrollTo(0, 0);
}

async function loadBlock(slug) {
    showView('block');

    // D-11: reset expand state on every entry into a block page. The Wave 3
    // idle poll (plan 04-05) reads this flag to choose limit(30) vs unbounded.
    timelineExpanded = false;

    // Fire the blocks-row + timeline-entries queries in parallel (D-16). Per
    // D-17 NO defensive filters: no .eq('status', 'published') on blocks, no
    // .neq('block_slug', 'unsorted') on timeline — RLS is the boundary. The
    // .eq('block_slug', slug) filter is functional scoping, not security.
    var blockRes, timelineRes;
    var pair = await Promise.all([
        sb.schema('economy_map').from('blocks').select('*').eq('slug', slug).single(),
        sb.schema('economy_map').from('timeline_entries').select('block_slug,event_date,what_shifted,why_it_mattered,source_url').eq('block_slug', slug).order('event_date', { ascending: false }).limit(30)
    ]);
    blockRes = pair[0];
    timelineRes = pair[1];

    if (blockRes.error || !blockRes.data) {
        document.getElementById('block-content').innerHTML = '<p style="color:var(--text-secondary);">Block not found.</p>';
        updateHero('Block Not Found', '');
        console.error('loadBlock error:', blockRes.error);
        return;
    }

    // Timeline query failures degrade gracefully — the block still renders, just
    // without Evolution entries.
    var timelineEntries = (timelineRes.error || !timelineRes.data) ? [] : timelineRes.data;

    // Conditionally fetch the published body (D-10 / D-17). Per D-17 NO
    // .eq('status', 'published') — RLS only exposes published versions to anon.
    // If the FK target doesn't satisfy RLS, this returns null and we fall through
    // to the body-hidden path.
    var bodyMd = null;
    if (blockRes.data.current_body_version_id) {
        var bodyRes = await sb.schema('economy_map').from('block_body_versions').select('body_md').eq('id', blockRes.data.current_body_version_id).single();
        if (!bodyRes.error && bodyRes.data) bodyMd = bodyRes.data.body_md;
    }

    // Stash for the Wave 3 idle poll (plan 04-05).
    window.currentBlock = blockRes.data;
    window.currentTimelineEntries = timelineEntries;

    // Hero per D-02: title + ('synthesized ' + date) when non-null, else no date.
    var dateText = blockRes.data.last_synthesized_at ? 'synthesized ' + formatDate(blockRes.data.last_synthesized_at) : '';
    updateHero(blockRes.data.title, dateText);

    renderBlock(blockRes.data, bodyMd, timelineEntries);
    window.scrollTo(0, 0);

    // Wave 3 (plan 04-05): start the visibility-aware 60s Evolution idle poll
    // (D-05/D-06/D-07). The block-not-found branch above returns BEFORE here, so
    // the poll only starts on the success path.
    startEvolutionPoll(slug);
}

// Six-part block-page composition (D-08): Title → tension → body → Evolution.
function renderBlock(block, bodyMd, entries) {
    // A. Header — always renders. D-09 inline pill, right-aligned (CSS). The
    //    header carries data-accent so the cascade resolves --accent-tier for
    //    the pill child.
    var headerHtml =
        '<header class="block-header" data-accent="' + escapeHtml(block.accent) + '">' +
            '<h1>' + escapeHtml(block.title) + '</h1>' +
            renderMaturityPill(block) +
        '</header>';

    // B. Tension — D-10 quiet hide when the seed placeholder. Exact-string match
    //    against LIVE_TENSION_PLACEHOLDER (Phase 2 D-21 em-dash U+2014).
    var tensionHtml = '';
    if (block.live_tension && block.live_tension !== LIVE_TENSION_PLACEHOLDER) {
        tensionHtml = '<section class="block-tension">' + escapeHtml(block.live_tension) + '</section>';
    }

    // C. Body — D-10 hide when null/missing; D-18 marked.parse (the only path
    //    that bypasses escapeHtml — same precedent as renderArticle()). Residual
    //    XSS-via-markdown accepted under threat T-04-03-01; the Phase 9 publish
    //    gate (operator approval) is the compensating control.
    var bodyHtml = '';
    if (bodyMd) {
        bodyHtml = '<section class="block-body">' + marked.parse(bodyMd) + '</section>';
    }

    // D. Evolution — always renders (even with zero entries). Newest-first per
    //    RNDR-07 (the .order() clause already sorted the array). 30-cap +
    //    show-all per D-11: the button appears only when the result hit the cap
    //    and we are not already expanded.
    var evolutionHtml =
        '<section class="evolution">' +
            '<h2>Evolution</h2>' +
            '<div id="evolution-entries">' + renderTimelineEntries(entries, timelineExpanded) + '</div>' +
            (entries.length === 30 && !timelineExpanded
                ? '<button class="timeline-show-all" onclick="expandTimeline()">Show all (' + entries.length + ' or more) ↓</button>'
                : '') +
        '</section>';

    // E. Compose. The ← Map back-link lives in the static plan-04-01 markup
    //    (sibling to #block-content), so the renderer does not emit it.
    document.getElementById('block-content').innerHTML = headerHtml + tensionHtml + bodyHtml + evolutionHtml;
}

// Evolution entry list — matches tokens-preview.html lines 114-125 (with source)
// and 128-137 (without source). Newest-first ordering is already in the array.
// Factored out so the Wave 3 idle poll (plan 04-05) can re-use it.
function renderTimelineEntries(entries, expanded) {
    if (!entries || entries.length === 0) {
        // Graceful empty state — distinct from D-10 hide-section; Evolution always
        // renders per D-08, just with this message when there are no entries yet.
        return '<p style="color:var(--text-secondary);">No timeline entries yet.</p>';
    }
    return entries.map(function(e) {
        var hasSource = (typeof e.source_url === 'string' && e.source_url.length > 0);
        // event_date already goes through formatDate; defensively escapeHtml the
        // result. what_shifted / why_it_mattered / source_url all escaped.
        var dateText = escapeHtml(formatDate(e.event_date));
        var line1 =
            '<div class="timeline-line1">' +
                '<time class="timeline-date">' + dateText + '</time>' +
                '<span class="timeline-sep">·</span>' +
                '<span class="timeline-what">' + escapeHtml(e.what_shifted) + '</span>' +
            '</div>';
        var line2Inner = '<span class="timeline-why">' + escapeHtml(e.why_it_mattered) + '</span>';
        if (hasSource) {
            line2Inner += '<a class="timeline-source" href="' + escapeHtml(e.source_url) + '" target="_blank" rel="noopener noreferrer">source ↗</a>';
        }
        var line2 = '<div class="timeline-line2">' + line2Inner + '</div>';
        // Source-null variant omits the data-source attribute entirely (T-04-03-03;
        // style-map.css lines 91-94 contract).
        var open = hasSource
            ? '<article class="timeline-entry" data-source="' + escapeHtml(e.source_url) + '">'
            : '<article class="timeline-entry">';
        return open + line1 + line2 + '</article>';
    }).join('');
}

// Show-all expand (D-11) — one-shot. Top-level declaration so the inline
// onclick="expandTimeline()" can reach it (matches scrollToSubscribe pattern).
async function expandTimeline() {
    if (!window.currentBlock) return;
    timelineExpanded = true;
    var slug = window.currentBlock.slug;
    var res = await sb.schema('economy_map').from('timeline_entries').select('block_slug,event_date,what_shifted,why_it_mattered,source_url').eq('block_slug', slug).order('event_date', { ascending: false });
    if (res.error || !res.data) return;
    window.currentTimelineEntries = res.data;
    document.getElementById('evolution-entries').innerHTML = renderTimelineEntries(res.data, true);
    var btn = document.querySelector('.timeline-show-all');
    if (btn) btn.remove();  // one-shot per D-11
}

// Status page — the maturity snapshot surface (RNDR-03). Reads the SAME
// economy_map.blocks source as the hub (RNDR-04 one source of truth), trimmed to
// the columns a status row needs (drops live_tension + current_body_version_id
// vs loadHub). Per D-15 rows are non-clickable divs; per D-17 NO defensive
// .eq('status', ...) filter — RLS is the boundary.
async function loadStatus() {
    showView('status');

    var { data, error } = await sb
        .schema('economy_map')
        .from('blocks')
        .select('slug,title,subtitle,accent,tier,sort_order,maturity,last_synthesized_at')
        .order('sort_order', { ascending: true });

    if (error || !data || data.length === 0) {
        document.getElementById('status-content').innerHTML = '<p style="color:var(--text-secondary);font-size:15px;padding:20px 24px;">Status data unavailable.</p>';
        updateHero(STATUS_PAGE_HEADER, '');
        console.error('loadStatus error:', error);
        return;
    }

    // Stash for symmetry with the other loaders (status has no re-render hooks in
    // v1 — no setMode dependency, no poll — but the assignment matches the pattern).
    window.currentStatusBlocks = data;

    // Hero per D-02: STATUS_PAGE_HEADER + 'updated <NOW>'. If the operator finds
    // the "updated NOW" affordance noisy, that is a CSS-only follow-up.
    updateHero(STATUS_PAGE_HEADER, 'updated ' + formatDate(new Date().toISOString()));

    renderStatus(data);
}

// Status renderer — one snapshot row per block, tier-grouped (D-15). Same three
// sections as the hub. Rows are <div>s, NOT links (status is the snapshot
// surface; the hub is navigation). Reuses the module-scoped renderMaturityPill.
function renderStatus(data) {
    // Group by tier the same way renderHub does. The query is already
    // sort_order-ascending, so each filtered array preserves seed order.
    var substrateBlocks = data.filter(function(b) { return b.tier === 'substrate'; });
    var behaviorBlocks = data.filter(function(b) { return b.tier === 'behavior'; });
    var frameBlocks = data.filter(function(b) { return b.tier === 'frame'; });

    // Single row (D-15): pill + title + (optional) subtitle + synth timestamp.
    // data-accent drives the left-border stripe via the --accent-tier cascade.
    // Every DB string and the computed synthText passes through escapeHtml.
    function renderStatusRow(b) {
        var synthText = b.last_synthesized_at
            ? 'synthesized ' + formatDate(b.last_synthesized_at)
            : 'never synthesized';
        return '<div class="status-row" data-accent="' + escapeHtml(b.accent) + '">' +
                   renderMaturityPill(b) +
                   '<div class="status-title">' + escapeHtml(b.title) + '</div>' +
                   (b.subtitle ? '<div class="status-subtitle">' + escapeHtml(b.subtitle) + '</div>' : '') +
                   '<time class="status-synth">' + escapeHtml(synthText) + '</time>' +
               '</div>';
    }

    // Tier section wrapper — <section class="tier-section"> with a
    // <h2 class="tier-label"> heading, same as renderHub. Skip empty arrays
    // (defensive — the seed always fills all three tiers).
    function tierSection(label, blocks) {
        if (!blocks.length) return '';
        return '<section class="tier-section">' +
                   '<h2 class="tier-label">' + label + '</h2>' +
                   blocks.map(renderStatusRow).join('') +
               '</section>';
    }

    var html =
        tierSection(TIER_LABELS.substrate, substrateBlocks) +
        tierSection(TIER_LABELS.behavior, behaviorBlocks) +
        tierSection(TIER_LABELS.frame, frameBlocks);

    document.getElementById('status-content').innerHTML = html;
    window.scrollTo(0, 0);
}

// ─── Evolution Idle Poll (Phase 4 plan 04-05) ─────────────────────────────────

// Visibility-aware 60s idle poll that refreshes ONLY the Evolution section on a
// block page (D-05 no Realtime, D-06 timeline-only, D-07 60s + visibility-aware,
// D-11 respects timelineExpanded). RNDR-06: a new timeline_entries insert appears
// within ~60s while the operator stays on the block page.

// Clear any active poll. Idempotent — safe to call when no handle is set.
function stopEvolutionPoll() {
    if (evolutionPollHandle !== null) {
        clearInterval(evolutionPollHandle);
        evolutionPollHandle = null;
    }
}

// Re-query timeline_entries for the given slug and repaint #evolution-entries
// (matches the renderArticle/renderList innerHTML-replace idiom — PATTERNS
// §"No analog found" mitigation row 3). Async; the interval callback fires it
// fire-and-forget. Guards: visibility (D-07) and a hash/slug re-check (race —
// the operator may have navigated away between the tick and this fn running).
async function pollEvolution(slug) {
    if (document.visibilityState !== 'visible') return;  // D-07 visibility guard
    if (!window.location.hash.startsWith('#/map/' + slug)) return;  // race re-check
    // D-06: re-query ONLY timeline_entries — never blocks / block_body_versions.
    var query = sb.schema('economy_map').from('timeline_entries')
        .select('block_slug,event_date,what_shifted,why_it_mattered,source_url')
        .eq('block_slug', slug)
        .order('event_date', { ascending: false });
    if (!timelineExpanded) query = query.limit(30);  // D-11 — respect expand-state
    var { data, error } = await query;
    if (error || !data) return;  // graceful no-op on transient error
    window.currentTimelineEntries = data;
    var container = document.getElementById('evolution-entries');
    if (container) container.innerHTML = renderTimelineEntries(data, timelineExpanded);
    // Keep the Show-all button in sync with the (possibly changed) result. When
    // collapsed and the cap is hit but no button exists, append one; when
    // expanded, remove any leftover button (matches expandTimeline's one-shot).
    var btn = document.querySelector('.timeline-show-all');
    if (!timelineExpanded && data.length === 30 && !btn) {
        var evolutionSection = document.querySelector('.evolution');
        if (evolutionSection) {
            var newBtn = document.createElement('button');
            newBtn.className = 'timeline-show-all';
            newBtn.setAttribute('onclick', 'expandTimeline()');
            newBtn.innerHTML = 'Show all (' + data.length + ' or more) ↓';
            evolutionSection.appendChild(newBtn);
        }
    }
    if (timelineExpanded && btn) {
        btn.remove();
    }
}

// Start a fresh 60s poll for the given slug. Defensively stops any prior handle so
// navigating between blocks never leaks a stale interval (T-04-05-01 / -04). The
// inner callback is non-async and fires-and-forgets the async pollEvolution.
function startEvolutionPoll(slug) {
    stopEvolutionPoll();  // defensive — ensure no stale handle
    evolutionPollHandle = setInterval(function() {
        pollEvolution(slug);
    }, 60000);  // D-07 cadence floor
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

// Idle-poll cleanup — a SIBLING listener to the routing one above (kept separate
// per PATTERNS §"#8 Init"). Fires after route() (registration order). Stops the
// Evolution poll whenever the new hash leaves the #/map/<slug> space (e.g. to
// #/map, #/status, #/). Navigating to a DIFFERENT block keeps the '#/map/' prefix
// match, so this does NOT stop it — but the subsequent loadBlock() → startEvolutionPoll()
// defensively stops the prior handle and starts a fresh one for the new slug.
window.addEventListener('hashchange', function() {
    if (!window.location.hash.startsWith('#/map/')) {
        stopEvolutionPoll();
    }
});

// Optional (D-07): trigger an immediate refresh when the tab becomes visible so
// the operator does not wait up to 60s for the next tick after returning. The
// poll's inner visibility guard already short-circuits ticks while hidden; this
// only adds a one-shot catch-up. The 60s cadence floor is unchanged.
window.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'visible'
        && evolutionPollHandle !== null
        && window.currentBlock
        && window.location.hash.startsWith('#/map/')) {
        pollEvolution(window.currentBlock.slug);
    }
});
