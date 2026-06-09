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

// Phase 17 (D-04): dormant-in-prod preview flag. Read off the URL with the SAME
// idiom as getInitialMode() (:49) — `?preview=1` (or `=true`) flips it on. It
// gates BOTH the block + hub draft-fetch fallbacks (D-03). DOUBLE-SAFE: in
// production the param is absent (flag stays false) AND published-only RLS
// independently returns no draft to the anon key — either alone makes the new
// path a no-op, so the deployed app.js renders byte-for-byte as today. The
// local-only service_role preview container (Phase 17-02) sets ?preview=1 to
// see the loaded-but-unpublished drafts. No new route/view/component — a
// boolean read only.
const PREVIEW_ENABLED = (function () {
    var p = new URL(window.location).searchParams.get('preview');
    return p === '1' || p === 'true';
})();

// Phase 17 (D-06c, HUB-01) — code-trim the hub draft body's prose block-list so
// it is NOT duplicated by the card grid. Operates on the markdown STRING before
// marked.parse (simpler + safer than post-render DOM surgery). The loaded hub
// body (.planning/docs/00-hub.md) is: thesis + `## How to read this map`
// framing, then the `## Tier 1 — The Substrate` / `## Tier 2 — The Behavior`
// prose block-list (the 7 [Title →](#/map/<slug>) links — the duplication
// source), then `## The thesis, restated`. Keep the head through the end of the
// How-to-read section (cut on the literal `## Tier 1` heading), then re-append
// the closing `## The thesis, restated` tail (Claude's Discretion default keeps
// the restated thesis). Pure helper — no DB write, the loaded draft is
// untouched/reversible. Returns the input unchanged if the cut heading is absent
// (defensive: never silently drops content it cannot bound).
function trimHubBody(md) {
    if (!md) return md;
    var TIER1 = '## Tier 1';
    var RESTATED = '## The thesis, restated';
    var cut = md.indexOf(TIER1);
    if (cut === -1) return md;            // cut-point absent → leave body intact
    var head = md.slice(0, cut).replace(/\s*(?:---\s*)?$/, '').trimEnd();
    var tailIdx = md.indexOf(RESTATED, cut);
    if (tailIdx === -1) return head;      // no restated-thesis tail → head only
    var tail = md.slice(tailIdx).trimEnd();
    return head + '\n\n' + tail + '\n';
}

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

    // Body class — content re-render selector only (D-03). Phase 11 decoupled the
    // palette to :root; this class no longer drives CSS variables/theme, it only
    // re-renders the dual-mode list/article content below.
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
    if (hash.startsWith('#/about')) {
        return { view: 'about' };
    }
    return { view: 'list' };
}

function showView(viewName) {
    document.getElementById('list-view').style.display = viewName === 'list' ? 'block' : 'none';
    document.getElementById('reader-view').style.display = viewName === 'reader' ? 'block' : 'none';
    document.getElementById('map-view').style.display = viewName === 'map' ? 'block' : 'none';
    document.getElementById('block-view').style.display = viewName === 'block' ? 'block' : 'none';
    document.getElementById('status-view').style.display = viewName === 'status' ? 'block' : 'none';
    var aboutView = document.getElementById('about-view');
    if (aboutView) aboutView.style.display = viewName === 'about' ? 'block' : 'none';

    // The Technical/Strategic toggle lives ONLY inside the Newsletter list (TGL-01,
    // D-01). Its host is the .hero block, scoped to the list route below; these
    // belt-and-suspenders display lines keep the toggle/subtitle hidden off-list.
    // Defensive null-checks per PATTERNS §3.
    var showToggle = (viewName === 'list');
    var toggle = document.querySelector('.mode-toggle');
    if (toggle) toggle.style.display = showToggle ? 'inline-flex' : 'none';
    var subtitle = document.getElementById('mode-subtitle');
    if (subtitle) subtitle.style.display = showToggle ? 'block' : 'none';

    // The .hero is the list-scoped minimal D3 header (it hosts the toggle). Render
    // it ONLY on the list route (TGL-01); the reader/map/block/status/about views
    // carry their own headers. Phase 13 owns the map/status hero behavior.
    var hero = document.querySelector('.hero');
    if (hero) hero.style.display = viewName === 'list' ? 'block' : 'none';
}

// ─── List View ───────────────────────────────────────────────────────────────

function renderList(data) {
    if (!data || data.length === 0) {
        document.getElementById('newsletter-list').innerHTML =
            '<div class="content-area"><p class="entry-preview">No newsletters published yet.</p></div>';
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
            '<div class="section-label">EDITION #' + n.edition_number + ' · ' + formatDate(n.published_at) + '</div>' +
            '<a href="#/edition/' + n.edition_number + '" class="entry-title">' + escapeHtml(title) + '</a>' +
            '<p class="entry-preview">' + escapeHtml(excerpt) + '</p>' +
            '</div>';
    }).join('');

    document.getElementById('newsletter-list').innerHTML = html;
}

async function loadList() {
    showView('list');
    // Set the hero synchronously so the previous section's title (e.g. the hub
    // HUB_STORYLINE) doesn't flash here during the async fetch. renderList()
    // refines the date once data arrives.
    updateHero('AI Agents Pulse', '');
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

    // Update hero with edition info (harmless on the reader route — the .hero is
    // list-scoped post-12-02 and not visible here; the article carries its own
    // magazine header below. Non-list callers still rely on updateHero()).
    updateHero(title, 'Edition #' + data.edition_number + ' \u00b7 ' + date);

    var banner = '';
    if (data.status === 'preview') {
        banner = '<div class="preview-banner">PREVIEW — NOT YET PUBLISHED</div>';
    }

    // Magazine header (D-05) — the reader view's own header, sitting under the
    // static "← Back to Newsletter" control in #reader-view. Mono .eyebrow kicker,
    // serif .page-title display title, mono byline. The {Technical|Strategic} label
    // is resolved from MODES (not hardcoded); every DB-derived string (title) is
    // escapeHtml'd exactly as the list rows are (edition_number is numeric).
    var sep = ' ' + String.fromCharCode(0xB7) + ' ';
    var modeLabel = MODES[currentMode].label;
    var header =
        '<div class="article-header">' +
            '<p class="eyebrow">Edition #' + data.edition_number + sep + modeLabel + '</p>' +
            '<h1 class="page-title">' + escapeHtml(title) + '</h1>' +
            '<p class="byline">Edition #' + data.edition_number + sep + date + sep + modeLabel + '</p>' +
        '</div>';

    var rendered = marked.parse(content);
    document.getElementById('newsletter-content').innerHTML = header + banner + rendered;
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

// CR-01: escapeHtml only HTML-entity-encodes — it does NOT block dangerous URL
// schemes. A javascript:/data: source_url survives escaping and would execute in
// an href. Gate every URL sink through this http(s)-only allowlist before render.
function safeHttpUrl(url) {
    if (typeof url !== 'string') return null;
    return /^https?:\/\//i.test(url.trim()) ? url : null;
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
function renderMaturityPill(b, deferred) {
    // Phase 13 (D-05): the per-tier accent attribute is dropped — the cascade
    // it fed is retired; the pill recolors to the single --accent via CSS. A
    // deferred block (no synthesized body) forces data-stage="0" so all 5
    // segments fall through to the --line-strong empty fill (MAP-04 empty dots).
    var stage = deferred ? 0 : (MATURITY_STAGE[b.maturity] || 1);
    var label = deferred
        ? 'Maturity: deferred (not yet synthesized)'
        : 'Maturity: ' + escapeHtml(b.maturity) + ' (' + stage + ' of 5)';
    return '<div class="maturity-pill" data-stage="' + stage + '" aria-label="' + label + '">' +
               '<span class="seg"></span><span class="seg"></span><span class="seg"></span><span class="seg"></span><span class="seg"></span>' +
           '</div>';
}

// ─── Map Loaders (Phase 4 — stubs; renderers ship in Wave 2) ──────────────────

// Stub loaders so route() resolves without ReferenceError. Each flips view
// visibility via showView() so the shell works before the Wave 2 renderers
// plug in the data + markup.
async function loadHub() {
    showView('map');
    // Phase 13 (D-06): the hub header renders inside #map-view .content-area in
    // renderHub() — the shared .hero is scoped to the list route (Phase 12), so
    // no updateHero() call here. The grid fills in once data arrives.

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
            '<p class="entry-preview" style="color:var(--ink-soft);">Map data unavailable.</p>';
        return;
    }

    window.currentBlocks = data;

    // Phase 17 (D-06a, HUB-01) — preview-only hub draft body. Fetched the SAME
    // way as the Task-2 D-03 block fallback but for slug 'agent-economy', gated
    // by PREVIEW_ENABLED. DORMANT in prod (no flag) AND a NO-OP for anon even if
    // reached (RLS exposes only status='published'). Graceful-degrade to null on
    // any error/empty → renderHub falls back to the HUB_STORYLINE constant.
    var hubBodyMd = null;
    if (PREVIEW_ENABLED) {
        var hubRes = await sb.schema('economy_map')
            .from('block_body_versions')
            .select('body_md')
            .eq('block_slug', 'agent-economy')
            .eq('status', 'draft')
            .order('created_at', { ascending: false })
            .limit(1);
        if (!hubRes.error && hubRes.data && hubRes.data.length) hubBodyMd = hubRes.data[0].body_md;
    }

    // Phase 18 (D-01): prod published-hub-body fetch — mirrors the loadBlock
    // published path (:674-677), flag-INDEPENDENT (NOT inside if (PREVIEW_ENABLED)),
    // so prod renders the PUBLISHED hub article instead of the hardcoded
    // HUB_STORYLINE constant once the hub body is published (D-01/D-02). The hub
    // row is resolved from the EXISTING loadHub blocks select above (no separate
    // hub-row read): the select reads all rows ordered by sort_order with NO tier
    // filter, so the 'agent-economy' row (tier 'hub', migration 043) is returned.
    // Gated on !hubBodyMd so the Phase-17 preview DRAFT fetch above keeps
    // precedence in preview mode — the exact draft-first/published-fallback
    // precedence loadBlock uses (:655-677). Per D-16 sb.schema('economy_map') sets
    // Accept-Profile automatically; per D-17 NO defensive .eq('status','published')
    // — anon RLS exposes ONLY published versions (the boundary). Graceful-degrade:
    // any error/empty leaves hubBodyMd null, never throws (mirrors :676).
    //
    // DOUBLE-SAFE deploy-first no-op proof (D-04 — same reasoning as the Phase-17
    // preview comment at :48-60): agent-economy.current_body_version_id is NULL
    // until the Phase-18 publish batch runs → hubRow.current_body_version_id is
    // null → this fetch is skipped → hubBodyMd stays null → renderHub falls back to
    // the HUB_STORYLINE constant. So shipping this app.js is a PROVABLE visual
    // no-op pre-publish (the NULL pointer → HUB_STORYLINE fallback is the proof).
    // AND independently, anon RLS exposes only status='published' versions, so even
    // a non-null pointer resolves only to published content — never a draft. No new
    // route/view/component/CSS class and no new blocks-select column: the only
    // behavioral change is populating hubBodyMd from the published path.
    var hubRow = data.find(function (b) { return b.slug === 'agent-economy'; });
    if (!hubBodyMd && hubRow && hubRow.current_body_version_id) {
        var hubBodyRes = await sb.schema('economy_map').from('block_body_versions')
            .select('body_md').eq('id', hubRow.current_body_version_id).single();
        if (!hubBodyRes.error && hubBodyRes.data) hubBodyMd = hubBodyRes.data.body_md;
    }

    // Phase 17 (preview-only) — draft proposed_maturity per loaded block.
    // blocks.maturity is stale until the Phase-18 publish watermark (mig 038), so
    // the cards must read the draft's proposed_maturity to preview publish-ready,
    // and a draft-bearing block is no longer rendered DEFERRED. One query,
    // flag-gated; DORMANT in prod (no flag), NO-OP for anon (RLS exposes only
    // published). Migration 041 guarantees at most one open draft per slug.
    var draftMaturity = null;
    var draftSlugs = null;
    if (PREVIEW_ENABLED) {
        var dmRes = await sb.schema('economy_map')
            .from('block_body_versions')
            .select('block_slug,proposed_maturity')
            .eq('status', 'draft');
        if (!dmRes.error && dmRes.data) {
            draftMaturity = {};
            draftSlugs = {};
            // A draft row for a slug means a loaded draft body exists — the same
            // signal loadBlock keys body rendering off — so the card is NOT
            // deferred in preview. proposed_maturity may be null on a draft; the
            // pill then falls back to blocks.maturity rather than forcing DEFERRED.
            dmRes.data.forEach(function(r) {
                draftSlugs[r.block_slug] = true;
                if (r.proposed_maturity) draftMaturity[r.block_slug] = r.proposed_maturity;
            });
        }
    }

    renderHub(data, hubBodyMd, draftMaturity, draftSlugs);
}

function renderHub(data, hubBodyMd, draftMaturity, draftSlugs) {
    // 1. Updated stamp — latest last_synthesized_at across all blocks (D-06).
    //    ISO string-sort orders correctly; omit the stamp entirely when every
    //    block has a null last_synthesized_at (v1 state). Phase 13: the hub
    //    header renders INSIDE #map-view .content-area, not via updateHero()
    //    (Phase 12 scoped the shared .hero to the list route — PATTERNS gotcha).
    var latest = data.map(function(b) { return b.last_synthesized_at; }).filter(Boolean).sort().pop();
    var subline = latest
        ? '<p class="hero-date">updated ' + escapeHtml(formatDate(latest)) + '</p>'
        : '';

    // 2. Group by tier. The query is already sort_order-ascending, so each
    //    filtered array preserves the seed order (Phase 2 D-23): substrate 1-3,
    //    behavior 4-6, frame 7.
    var substrateBlocks = data.filter(function(b) { return b.tier === 'substrate'; });
    var behaviorBlocks = data.filter(function(b) { return b.tier === 'behavior'; });
    var frameBlocks = data.filter(function(b) { return b.tier === 'frame'; });

    // 3. Single card — whole <a> is the click target (D-14). encodeURIComponent
    //    on the slug is defense-in-depth; every DB string is escapeHtml'd. A
    //    block with no synthesized body (current_body_version_id null) renders
    //    as a full-width DEFERRED card with empty dots + a "· DEFERRED" tag
    //    (MAP-04, D-04). The deferred state is derived in JS from a column
    //    already in the loadHub select — NO .eq('status',…) filter (D-17, RLS).
    function renderTile(b) {
        // Phase 17 (preview-only): a draft-bearing block previews as publish-ready
        // — never DEFERRED (keyed off draft-body existence, the same signal
        // loadBlock uses), and its pill reflects the draft's proposed_maturity when
        // present (blocks.maturity is stale pre-publish). Both maps are null in prod
        // → identical pre-change behavior (deferred keyed off current_body_version_id).
        var hasDraftBody = !!(draftSlugs && draftSlugs[b.slug]);
        var previewMaturity = (draftMaturity && draftMaturity[b.slug]) ? draftMaturity[b.slug] : null;
        var deferred = !b.current_body_version_id && !hasDraftBody;
        var pillArg = previewMaturity ? { maturity: previewMaturity } : b;
        var cls = deferred ? 'card card-deferred' : 'card';
        var dotsRow = deferred
            ? '<div class="card-dots-row">' + renderMaturityPill(pillArg, true) +
                  '<span class="deferred-tag">· DEFERRED</span></div>'
            : renderMaturityPill(pillArg, false);
        return '<a href="#/map/' + encodeURIComponent(b.slug) + '" class="' + cls + '">' +
                   '<h3 class="tile-title">' + escapeHtml(b.title) + '</h3>' +
                   '<p class="tile-subtitle">' + escapeHtml(b.subtitle) + '</p>' +
                   dotsRow +
               '</a>';
    }

    // 4. Tier section wrapper — emits a <section class="tier-section"> with a
    //    <h2 class="tier-label"> heading ABOVE a <div class="grid"> of cards
    //    (MAP-01/03; the label sits above the grid, not inside it). Skips an
    //    empty array so no dangling heading appears (defensive; the seed always
    //    fills all three tiers).
    function tierSection(label, blocks) {
        if (!blocks.length) return '';
        return '<section class="tier-section">' +
                   '<h2 class="tier-label">' + label + '</h2>' +
                   '<div class="grid">' +
                       blocks.map(renderTile).join('') +
                   '</div>' +
               '</section>';
    }

    // 5. In-content hub header (D-06) + three tier grids, written to the
    //    #map-view's .content-area. Order: serif "The Agent Economy" page-title,
    //    optional mono "updated {date}" sub-line (only when latest exists),
    //    hub intro, then the tier grids. No eyebrow kicker (UI-SPEC §5).
    //    Phase 17 (D-06a/c, HUB-01): when a hub draft body is present (preview
    //    only), render the trimHubBody()'d intro via marked.parse (the same body
    //    path as :586 — no new capability); the trim drops the Tier-1/Tier-2
    //    prose block-list so it appears ONCE, as the cards. Graceful fallback to
    //    the escapeHtml'd HUB_STORYLINE constant pre-publish (P15-D-04) — the
    //    constant is NOT deleted. The marked.parse'd hub intro is also where the
    //    7 hub→block #/map/<slug> links would render, but click-through is
    //    already satisfied by the cards; the trimmed intro keeps the thesis +
    //    two-tier framing only.
    var trimmedHubBody = trimHubBody(hubBodyMd);
    var hubIntroHtml = trimmedHubBody
        ? '<div class="hub-storyline">' + marked.parse(trimmedHubBody) + '</div>'
        : '<div class="hub-storyline">' + escapeHtml(HUB_STORYLINE) + '</div>';

    var html =
        '<h1 class="page-title">The Agent Economy</h1>' +
        subline +
        hubIntroHtml +
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
        document.getElementById('block-content').innerHTML = '<p style="font-family:var(--serif);color:var(--ink-soft);">Block not found.</p>';
        updateHero('Block Not Found', '');
        console.error('loadBlock error:', blockRes.error);
        return;
    }

    // Timeline query failures degrade gracefully — the block still renders, just
    // without Evolution entries.
    var timelineEntries = (timelineRes.error || !timelineRes.data) ? [] : timelineRes.data;

    // Body resolution. Phase 17 (D-03, LINK-01 + preview-maturity fix): in preview
    // mode the loaded DRAFT takes precedence so the page shows exactly what Phase
    // 18 will publish — its body AND its proposed_maturity (blocks.maturity stays
    // stale until the publish watermark, mig 038). Flag-gated: prod (no flag)
    // skips the draft entirely and takes the unchanged published path below, so
    // the deployed render is a byte-for-byte no-op. Migration 041 guarantees at
    // most ONE open draft per slug, so .limit(1)+array (NOT .single()) returns 0/1
    // cleanly; created_at is the append-ordering column (15-CONTRACT §Body
    // storage). The .eq('status','draft') is the deliberate, flag-gated INVERSE of
    // the D-17-forbidden defensive .eq('status','published') — functional scoping
    // for the preview-only path, never reachable for anon. Graceful-degrade: any
    // error/empty leaves bodyMd null, never throws. renderBlock's marked.parse
    // (:586) turns the in-body #/map/<slug> links into real <a href> (LINK-01).
    var bodyMd = null;
    if (PREVIEW_ENABLED) {
        var draftRes = await sb.schema('economy_map')
            .from('block_body_versions')
            .select('body_md,proposed_maturity')
            .eq('block_slug', slug)
            .eq('status', 'draft')
            .order('created_at', { ascending: false })
            .limit(1);
        if (!draftRes.error && draftRes.data && draftRes.data.length) {
            bodyMd = draftRes.data[0].body_md;
            // Preview the draft's proposed_maturity in the pill (blocks.maturity
            // is stale pre-publish). Overrides this local fetch row only.
            if (draftRes.data[0].proposed_maturity) blockRes.data.maturity = draftRes.data[0].proposed_maturity;
        }
    }

    // Published body (D-10 / D-17) — unchanged prod path. Per D-17 NO
    // .eq('status','published'); RLS exposes only published versions to anon. In
    // preview this is reached only when no draft was found above.
    if (!bodyMd && blockRes.data.current_body_version_id) {
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
    // A. Header — always renders. D-09 inline pill, right-aligned (CSS). Phase 13
    //    (D-05): the per-tier accent attribute is dropped — the cascade it fed is
    //    retired; the inline pill recolors to the single --accent via CSS.
    var headerHtml =
        '<header class="block-header">' +
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
        return '<p style="font-family:var(--serif);color:var(--ink-soft);">No timeline entries yet.</p>';
    }
    return entries.map(function(e) {
        // CR-01: only render the source link/attr when the URL is http(s). A
        // javascript:/data: URL fails safeHttpUrl and is dropped (no href, no
        // data-source) — escapeHtml alone would NOT make those schemes safe.
        var safeUrl = safeHttpUrl(e.source_url);
        var hasSource = safeUrl !== null;
        // event_date goes through formatDate; escapeHtml the result defensively.
        // what_shifted / why_it_mattered are HTML-escaped; source_url is both
        // scheme-validated (safeHttpUrl) and HTML-escaped.
        var dateText = escapeHtml(formatDate(e.event_date));
        var line1 =
            '<div class="timeline-line1">' +
                '<time class="timeline-date">' + dateText + '</time>' +
                '<span class="timeline-sep">·</span>' +
                '<span class="timeline-what">' + escapeHtml(e.what_shifted) + '</span>' +
            '</div>';
        var line2Inner = '<span class="timeline-why">' + escapeHtml(e.why_it_mattered) + '</span>';
        if (hasSource) {
            line2Inner += '<a class="timeline-source" href="' + escapeHtml(safeUrl) + '" target="_blank" rel="noopener noreferrer">source ↗</a>';
        }
        var line2 = '<div class="timeline-line2">' + line2Inner + '</div>';
        // Source-null (or unsafe-scheme) variant omits the data-source attribute
        // entirely (T-04-03-03; style-map.css lines 91-94 contract).
        var open = hasSource
            ? '<article class="timeline-entry" data-source="' + escapeHtml(safeUrl) + '">'
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
        document.getElementById('status-content').innerHTML = '<p style="font-family:var(--serif);color:var(--ink-soft);padding:20px 24px;">Status data unavailable.</p>';
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
    // Phase 13 (D-05): the per-tier accent attribute is dropped — the left-border
    // stripe recolors to the single --accent via CSS. Every DB string and the
    // computed synthText passes through escapeHtml.
    function renderStatusRow(b) {
        var synthText = b.last_synthesized_at
            ? 'synthesized ' + formatDate(b.last_synthesized_at)
            : 'never synthesized';
        return '<div class="status-row">' +
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

// ─── Nav Shell: route-derived active tab (NAV-02) ─────────────────────────────

// Map the getRoute() view string → the nav tab that should be active, per the
// UI-SPEC route→tab table (verbatim): list/reader → newsletter; map/block/status
// → map; about → about; unsubscribe → none. Active state is ROUTE-derived (called
// inside route() on load + every hashchange), NOT click-derived. Defensive
// null-checks per PATTERNS §3 — if no .tab elements exist, no-op safely.
function setActiveTab(view) {
    var VIEW_TO_TAB = {
        list: 'newsletter',
        reader: 'newsletter',
        map: 'map',
        block: 'map',
        status: 'map',
        about: 'about'
        // unsubscribe → undefined → no active tab (utility page)
    };
    var targetTab = VIEW_TO_TAB[view]; // undefined for unsubscribe / unknown
    var tabs = document.querySelectorAll('.tab');
    if (!tabs || !tabs.length) return;
    tabs.forEach(function(el) {
        var isActive = el.dataset.tab === targetTab;
        el.classList.toggle('active', isActive);
        if (isActive) {
            el.setAttribute('aria-current', 'page');
        } else {
            el.removeAttribute('aria-current');
        }
    });
}

// ─── Init ────────────────────────────────────────────────────────────────────

function route() {
    window.currentNewsletter = null;
    var r = getRoute();
    setActiveTab(r.view);
    switch (r.view) {
        case 'list': loadList(); break;
        case 'reader': loadEdition(r.edition); break;
        case 'unsubscribe': handleUnsubscribe(); break;
        case 'map': loadHub(); break;
        case 'block': loadBlock(r.slug); break;
        case 'status': loadStatus(); break;
        case 'about': showView('about'); window.scrollTo(0, 0); break;
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
