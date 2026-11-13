import json, os, re, sys, urllib.request, urllib.error

URL = os.environ.get("LP_MCP_URL", "").strip()
ACTION = os.environ.get("ACTION", "remonter")  # decouvrir | publier | remonter

ANNONCES = [
    {
        "marque": "RED by SFR",
        "cle": "red",
        "titre": "Jusqu'à 15 € offerts sur ta 1ère facture RED by SFR",
        "code": "REDB483D8F",
        "lien": "https://www.red-by-sfr.fr/?codeP=REDB483D8F",
        "texte": """🎁 Jusqu'à 15 € offerts sur ta 1ère facture RED by SFR !

✅ 15 € pour une RED Box (fibre) – 10 € pour un forfait mobile
✅ Sans engagement, cumulable avec les promos en cours

👉 Comment en profiter (2 min) :
1. Clique sur mon lien : https://www.red-by-sfr.fr/?codeP=REDB483D8F
2. Ou saisis le code REDB483D8F au moment de souscrire
3. Choisis ton forfait ou ta box, c'est tout !

💬 Je réponds vite à toutes tes questions par la messagerie du site. N'hésite pas !""",
    },
    {
        "marque": "BoursoBank",
        "cle": "bourso",
        "titre": "Jusqu'à 160 € offerts chez BoursoBank – ma prime va à une association",
        "code": "NAGA0360",
        "lien": "",
        "texte": """💚 Jusqu'à 160 € offerts chez BoursoBank… et ma prime part à une association !

Code parrain : NAGA0360

Éducateur, je reverse ma prime de parrain à une association.

👉 Comment faire :
1. Ouvre ton compte BoursoBank avec le code NAGA0360
2. Effectue ton 1er versement (il conditionne le montant de ta prime)
3. Reçois ta prime, et fais une bonne action au passage 🙏

💬 Une question ? Écris-moi, je réponds vite.""",
    },
    {
        "marque": "Hello bank",
        "cle": "hello",
        "titre": "Jusqu'à 330 € offerts chez Hello bank (offre flash jusqu'au 8 décembre)",
        "code": "",
        "lien": "",
        "texte": """🎁 Jusqu'à 330 € offerts chez Hello bank ! (offre flash jusqu'au 8 décembre)
💚 Et ma prime de parrain est reversée à une association !

✅ 130 € en argent + 200 € en bons d'achat (selon l'offre choisie)
✅ Banque en ligne du groupe BNP Paribas, appli simple et carte gratuite avec Hello One

👉 Comment faire :
1. Envoie-moi un message avec ton prénom, ton nom et ton e-mail
2. Je t'envoie l'invitation officielle Hello bank! depuis mon espace client
3. Ouvre ton compte via le lien reçu par e-mail, c'est tout !

💬 Éducateur, je réponds rapidement à toutes tes questions. Fais une bonne affaire… et une bonne action 🙏""",
    },
    {
        "marque": "Acheel",
        "cle": "acheel",
        "titre": "1 mois offert sur ton assurance Acheel avec le code NAGA0360",
        "code": "NAGA0360",
        "lien": "",
        "texte": """🎁 1 MOIS OFFERT sur ton assurance Acheel avec le code NAGA0360 !

✅ Assurance 100 % en ligne, prix doux et service client très réactif
✅ Je suis assurée chez eux pour mon animal et j'en suis ravie

👉 Comment en profiter :
1. Fais ton devis sur le site Acheel
2. Saisis le code NAGA0360 au moment de souscrire
3. Ton 1er mois est offert, c'est tout !

💬 Une question sur Acheel ou sur l'assurance animaux ? Écris-moi, je réponds vite.""",
    },
]

session = None
next_id = 0


def rpc(method, params=None, notify=False):
    global session, next_id
    body = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        body["params"] = params
    if not notify:
        next_id += 1
        body["id"] = next_id
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("MCP-Protocol-Version", "2025-06-18"); req.add_header("User-Agent", "robot-remontee/1.0 (client MCP)")
    if session:
        req.add_header("Mcp-Session-Id", session)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            session = r.headers.get("Mcp-Session-Id") or session
            raw = r.read().decode("utf-8", "replace")
            ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        sys.exit(f"ECHEC HTTP {e.code} sur {method} : {e.read().decode('utf-8', 'replace')[:500]}")
    if notify:
        return None
    msgs = []
    if "text/event-stream" in ctype:
        for line in raw.splitlines():
            if line.startswith("data:"):
                try:
                    msgs.append(json.loads(line[5:].strip()))
                except Exception:
                    pass
    else:
        msgs.append(json.loads(raw))
    for m in msgs:
        if m.get("id") == body["id"]:
            if "error" in m:
                raise RuntimeError(json.dumps(m["error"], ensure_ascii=False))
            return m.get("result")
    raise RuntimeError(f"Pas de reponse pour {method} : {raw[:300]}")


def call(tool, args):
    res = rpc("tools/call", {"name": tool["name"], "arguments": args})
    txt = "\n".join(c.get("text", "") for c in (res or {}).get("content", []) if c.get("type") == "text")
    if res and res.get("structuredContent"):
        txt += "\n" + json.dumps(res["structuredContent"], ensure_ascii=False)
    return bool(res and res.get("isError")), txt



def slug_candidates(text, cle):
    found = []
    pats = [r'slug["\']?\s*[:=]\s*["\']?([a-z0-9][a-z0-9-]*)',
            r'/(?:programmes?|parrainages?|offres?|p|code-parrainage)/([a-z0-9][a-z0-9-]*)',
            r'\(([a-z0-9][a-z0-9-]*)\)',
            r'`([a-z0-9][a-z0-9-]*)`']
    for p in pats:
        for m in re.findall(p, text, re.I):
            m = m.lower()
            if m.startswith(cle) and m not in found:
                found.append(m)
    return found


def main():
    if not URL:
        sys.exit("Secret LP_MCP_URL manquant.")
    print("Action :", ACTION)
    if ACTION == "remonter":
        print("Le Parrain ne propose pas de remontee via le connecteur : rien a faire.")
        return
    rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "robot-remontee", "version": "1.0"}})
    rpc("notifications/initialized", notify=True)
    tools = {t["name"]: t for t in (rpc("tools/list") or {}).get("tools", [])}
    print(f"{len(tools)} outil(s) Le Parrain.")
    if ACTION == "decouvrir":
        for n in tools:
            print(" -", n)
        return
    for need in ("search_programs", "create_announcement"):
        if need not in tools:
            sys.exit(f"ECHEC : outil {need} absent.")

    ok = 0
    for ad in ANNONCES:
        print(f"\n=== {ad['marque']}")
        err, res = call(tools["search_programs"], {"query": ad["marque"]})
        print("Recherche :", res[:700].replace("\n", " | "))
        cands = slug_candidates(res, ad["cle"])
        guess = re.sub(r"[^a-z0-9]+", "-", ad["marque"].lower()).strip("-")
        for g in (guess, guess.replace("-", "")):
            if g.startswith(ad["cle"]) and g not in cands:
                cands.append(g)
        print("Identifiants possibles :", cands)
        done = False
        for slug in cands[:4]:
            args = {"program": slug, "title": ad["titre"], "content": ad["texte"]}
            if ad["lien"]:
                args["referral_url"] = ad["lien"]
            if ad["code"]:
                args["referral_code"] = ad["code"]
            err, txt = call(tools["create_announcement"], args)
            low = txt.lower()
            if not err and "introuvable" not in low:
                print(f"PUBLIEE ({slug}) -> {txt[:300]}")
                ok += 1
                done = True
                break
            if re.search(r"d[ée]j[àa]|existe d[ée]j|already", low) and not re.search(r"introuvable|n'existe pas", low):
                print(f"Deja publiee ({slug}) -> {txt[:200]}")
                ok += 1
                done = True
                break
            print(f"  {slug} : {txt[:200]}")
        if not done:
            print(f"NON publiee : programme {ad['marque']} non trouve dans l'annuaire Le Parrain.")
    print(f"\nTermine : {ok}/{len(ANNONCES)} annonce(s) en ligne.")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
