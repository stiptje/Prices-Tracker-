#!/usr/bin/env python3
"""Builds data/retailers.json (+ .csv) and data/excluded.json.

This file is how the database was *seeded*. After the first build, data/retailers.json is the
source of truth: `python -m pricetracker.verify` rewrites verification fields in it, and you can
add retailers by editing it directly (or by adding a row here and re-running with --merge, which
keeps existing verification state).

Inclusion rule (see README): a retailer must be BASED IN EUROPE – headquartered in a European
country, or running the storefront through a registered European entity with local presence
(Amazon.de, Apple Store DE, Samsung DE …; flagged entity_basis="eu_subsidiary" so you can switch
them off in the UI). Shops located outside Europe that merely ship to Europe are in excluded.json.

Search templates:  {q} = url-encoded with '+',  {q_path} = url-encoded with %20,  {q_dash} = dash-joined.
search_confidence: "known"      = URL pattern I am confident about,
                   "unknown"    = no template; the app auto-discovers one (OpenSearch / search form /
                                  common platform patterns) the first time it is needed.
Everything starts as status="unverified": run  python -m pricetracker.verify --write  from a machine
with normal internet access to check each site and confirm its search URL.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pricetracker import config                      # noqa: E402
from pricetracker.retailers import EUROPE, Retailer, load_all, save_all, validate  # noqa: E402

K = "known"
U = "unknown"
ROWS: list[Retailer] = []


def R(id, name, cc, website, kind, hq, search=None, group="", cond="new", notes="",
      domain=None, sells=None):
    host = urlparse(website).hostname or ""
    dom = domain or (host[4:] if host.startswith("www.") else host)
    ROWS.append(Retailer(
        id=id, name=name, country=cc, website=website, domain=dom, kind=kind,
        hq_country=hq, entity_basis="headquartered" if hq in EUROPE else "eu_subsidiary",
        group=group, search_url=search, search_confidence=K if search else U,
        condition=cond, notes=notes,
        sells=sells or (["smartphones"] if kind in ("telecom_operator", "brand_store") else ["smartphones", "electronics"]),
    ))


EC, OE, CS, MP, GR, TO, BS, RF = (
    "electronics_chain", "online_electronics", "computer_specialist", "marketplace",
    "general_retail", "telecom_operator", "brand_store", "refurbished",
)

# =========================================================================== BELGIUM
R("coolblue-be", "Coolblue", "BE", "https://www.coolblue.be/nl", OE, "NL", "https://www.coolblue.be/nl/zoeken?query={q}", group="Coolblue")
R("mediamarkt-be", "MediaMarkt", "BE", "https://www.mediamarkt.be/nl", EC, "DE", "https://www.mediamarkt.be/nl/search.html?query={q}", group="MediaMarktSaturn (Ceconomy)")
R("krefel-be", "Krefel", "BE", "https://www.krefel.be/nl", EC, "BE")
R("vandenborre-be", "Vanden Borre", "BE", "https://www.vandenborre.be/", EC, "FR", group="Fnac Darty", notes="Belgian chain owned by Fnac Darty")
R("bol-be", "bol", "BE", "https://www.bol.com/be/nl/", MP, "NL", "https://www.bol.com/be/nl/s/?searchtext={q}", group="bol", notes="Marketplace: price shown is the featured offer")
R("fnac-be", "Fnac", "BE", "https://www.fnac.be/", EC, "FR", "https://www.fnac.be/SearchResult/ResultList.aspx?Search={q}", group="Fnac Darty")
R("amazon-be", "Amazon.com.be", "BE", "https://www.amazon.com.be/", MP, "US", "https://www.amazon.com.be/s?k={q}", group="Amazon", notes="Operated by Amazon EU S.à r.l. (Luxembourg); featured offer shown")
R("alternate-be", "Alternate", "BE", "https://www.alternate.be/", CS, "DE", "https://www.alternate.be/listing.xhtml?q={q}", group="Alternate")
R("ldlc-be", "LDLC Belgique", "BE", "https://www.ldlc.be/", CS, "FR", group="LDLC")
R("carrefour-be", "Carrefour Belgium", "BE", "https://www.carrefour.eu/nl", GR, "FR", group="Carrefour")
R("proximus-be", "Proximus", "BE", "https://www.proximus.be/", TO, "BE")
R("orange-be", "Orange Belgium", "BE", "https://www.orange.be/", TO, "BE", group="Orange")
R("telenet-be", "Telenet", "BE", "https://www.telenet.be/", TO, "BE", group="Liberty Global")
R("base-be", "BASE", "BE", "https://www.base.be/", TO, "BE", group="Telenet")
R("mobilevikings-be", "Mobile Vikings", "BE", "https://mobilevikings.be/", TO, "BE", group="Telenet")
R("backmarket-be", "Back Market", "BE", "https://www.backmarket.be/nl-be", RF, "FR", "https://www.backmarket.be/nl-be/search?q={q}", cond="refurbished", group="Back Market")
R("swappie-be", "Swappie", "BE", "https://swappie.com/be-nl/", RF, "FI", cond="refurbished", group="Swappie", domain="swappie.com")
R("refurbed-be", "refurbed", "BE", "https://www.refurbed.be/", RF, "AT", cond="refurbished", group="refurbed")
R("apple-be", "Apple Store", "BE", "https://www.apple.com/be-nl/", BS, "US", "https://www.apple.com/be-nl/search/{q_path}?src=serp", group="Apple", notes="Apple pages are not schema.org-annotated; results may be unavailable")
R("samsung-be", "Samsung Shop", "BE", "https://www.samsung.com/be/", BS, "KR", "https://www.samsung.com/be/search/?searchvalue={q}", group="Samsung")
R("xiaomi-be", "Xiaomi Store", "BE", "https://www.mi.com/be/", BS, "CN", group="Xiaomi", notes="Local EU storefront")
R("oneplus-be", "OnePlus Store", "BE", "https://www.oneplus.com/be", BS, "CN", group="OnePlus", notes="Local EU storefront")
R("google-be", "Google Store", "BE", "https://store.google.com/be", BS, "US", group="Google")
R("fairphone-be", "Fairphone Shop", "BE", "https://shop.fairphone.com/be", BS, "NL", group="Fairphone", domain="fairphone.com")
R("honor-be", "Honor", "BE", "https://www.honor.com/be/", BS, "CN", group="Honor", notes="Local EU storefront")
R("ebay-be", "eBay Belgium", "BE", "https://www.ebay.be/", MP, "US", "https://www.ebay.be/sch/i.php?_nkw={q}", group="eBay", notes="Marketplace; many private sellers and used items")

# =========================================================================== FRANCE
R("fnac-fr", "Fnac", "FR", "https://www.fnac.com/", EC, "FR", "https://www.fnac.com/SearchResult/ResultList.aspx?Search={q}", group="Fnac Darty")
R("darty-fr", "Darty", "FR", "https://www.darty.com/", EC, "FR", "https://www.darty.com/nav/recherche?text={q}", group="Fnac Darty")
R("boulanger-fr", "Boulanger", "FR", "https://www.boulanger.com/", EC, "FR", "https://www.boulanger.com/resultats?tr={q}")
R("cdiscount-fr", "Cdiscount", "FR", "https://www.cdiscount.com/", MP, "FR", "https://www.cdiscount.com/search/10/{q_dash}.html", group="Casino")
R("amazon-fr", "Amazon.fr", "FR", "https://www.amazon.fr/", MP, "US", "https://www.amazon.fr/s?k={q}", group="Amazon", notes="Operated by Amazon EU S.à r.l.; featured offer shown")
R("rakuten-fr", "Rakuten France", "FR", "https://fr.shopping.rakuten.com/", MP, "JP", "https://fr.shopping.rakuten.com/search/{q_path}", group="Rakuten", domain="rakuten.com", notes="Rakuten France SAS, Paris; marketplace")
R("ldlc-fr", "LDLC", "FR", "https://www.ldlc.com/", CS, "FR", "https://www.ldlc.com/recherche/{q_path}/", group="LDLC")
R("materiel-net", "Materiel.net", "FR", "https://www.materiel.net/", CS, "FR", "https://www.materiel.net/recherche/{q_path}/", group="LDLC")
R("rueducommerce-fr", "Rue du Commerce", "FR", "https://www.rueducommerce.fr/", OE, "FR")
R("grosbill-fr", "Grosbill", "FR", "https://www.grosbill.com/", CS, "FR")
R("topachat-fr", "TopAchat", "FR", "https://www.topachat.com/", CS, "FR")
R("cybertek-fr", "Cybertek", "FR", "https://www.cybertek.fr/", CS, "FR")
R("ubaldi-fr", "Ubaldi", "FR", "https://www.ubaldi.com/", OE, "FR")
R("sonvideo-fr", "Son-Vidéo.com", "FR", "https://www.son-video.com/", OE, "FR")
R("electrodepot-fr", "Electro Dépôt", "FR", "https://www.electrodepot.fr/", EC, "FR", "https://www.electrodepot.fr/catalogsearch/result/?q={q}")
R("but-fr", "BUT", "FR", "https://www.but.fr/", GR, "FR")
R("conforama-fr", "Conforama", "FR", "https://www.conforama.fr/", GR, "FR")
R("auchan-fr", "Auchan", "FR", "https://www.auchan.fr/", GR, "FR", "https://www.auchan.fr/recherche?text={q}")
R("carrefour-fr", "Carrefour", "FR", "https://www.carrefour.fr/", GR, "FR", "https://www.carrefour.fr/s?q={q}", group="Carrefour")
R("leclerc-fr", "E.Leclerc", "FR", "https://www.e.leclerc/", GR, "FR", "https://www.e.leclerc/recherche?q={q}")
R("cultura-fr", "Cultura", "FR", "https://www.cultura.com/", GR, "FR", "https://www.cultura.com/catalogsearch/result/?q={q}")
R("conrad-fr", "Conrad France", "FR", "https://www.conrad.fr/", CS, "DE", group="Conrad")
R("orange-fr", "Orange", "FR", "https://boutique.orange.fr/", TO, "FR", group="Orange", domain="orange.fr")
R("sfr-fr", "SFR", "FR", "https://www.sfr.fr/", TO, "FR", group="Altice France")
R("bouygues-fr", "Bouygues Telecom", "FR", "https://www.bouyguestelecom.fr/", TO, "FR")
R("free-fr", "Free Mobile", "FR", "https://mobile.free.fr/", TO, "FR", group="Iliad", domain="free.fr")
R("laposte-mobile-fr", "La Poste Mobile", "FR", "https://www.lapostemobile.fr/", TO, "FR")
R("backmarket-fr", "Back Market", "FR", "https://www.backmarket.fr/fr-fr", RF, "FR", "https://www.backmarket.fr/fr-fr/search?q={q}", cond="refurbished", group="Back Market")
R("certideal-fr", "Certideal", "FR", "https://www.certideal.com/", RF, "FR", cond="refurbished")
R("swappie-fr", "Swappie", "FR", "https://swappie.com/fr/", RF, "FI", cond="refurbished", group="Swappie", domain="swappie.com")
R("refurbed-fr", "refurbed", "FR", "https://www.refurbed.fr/", RF, "AT", cond="refurbished", group="refurbed")
R("apple-fr", "Apple Store", "FR", "https://www.apple.com/fr/", BS, "US", "https://www.apple.com/fr/search/{q_path}?src=serp", group="Apple", notes="Apple pages are not schema.org-annotated; results may be unavailable")
R("samsung-fr", "Samsung Shop", "FR", "https://www.samsung.com/fr/", BS, "KR", "https://www.samsung.com/fr/search/?searchvalue={q}", group="Samsung")
R("xiaomi-fr", "Xiaomi Store", "FR", "https://www.mi.com/fr/", BS, "CN", group="Xiaomi", notes="Local EU storefront")
R("oneplus-fr", "OnePlus Store", "FR", "https://www.oneplus.com/fr", BS, "CN", group="OnePlus", notes="Local EU storefront")
R("google-fr", "Google Store", "FR", "https://store.google.com/fr", BS, "US", group="Google")
R("fairphone-fr", "Fairphone Shop", "FR", "https://shop.fairphone.com/fr", BS, "NL", group="Fairphone", domain="fairphone.com")
R("motorola-fr", "Motorola", "FR", "https://www.motorola.fr/", BS, "US", group="Lenovo/Motorola", notes="Local EU storefront")
R("honor-fr", "Honor", "FR", "https://www.honor.com/fr/", BS, "CN", group="Honor", notes="Local EU storefront")
R("huawei-fr", "Huawei", "FR", "https://consumer.huawei.com/fr/", BS, "CN", group="Huawei", domain="huawei.com", notes="Local EU storefront")
R("ebay-fr", "eBay France", "FR", "https://www.ebay.fr/", MP, "US", "https://www.ebay.fr/sch/i.php?_nkw={q}", group="eBay", notes="Marketplace; many private sellers and used items")

# =========================================================================== NETHERLANDS
R("coolblue-nl", "Coolblue", "NL", "https://www.coolblue.nl/", OE, "NL", "https://www.coolblue.nl/zoeken?query={q}", group="Coolblue")
R("bol-nl", "bol", "NL", "https://www.bol.com/nl/nl/", MP, "NL", "https://www.bol.com/nl/nl/s/?searchtext={q}", group="bol", notes="Marketplace: price shown is the featured offer")
R("mediamarkt-nl", "MediaMarkt", "NL", "https://www.mediamarkt.nl/", EC, "DE", "https://www.mediamarkt.nl/nl/search.html?query={q}", group="MediaMarktSaturn (Ceconomy)")
R("amazon-nl", "Amazon.nl", "NL", "https://www.amazon.nl/", MP, "US", "https://www.amazon.nl/s?k={q}", group="Amazon", notes="Operated by Amazon EU S.à r.l.; featured offer shown")
R("bcc-nl", "BCC", "NL", "https://www.bcc.nl/", EC, "NL")
R("expert-nl", "Expert", "NL", "https://www.expert.nl/", EC, "NL")
R("wehkamp-nl", "Wehkamp", "NL", "https://www.wehkamp.nl/", GR, "NL")
R("alternate-nl", "Alternate", "NL", "https://www.alternate.nl/", CS, "DE", "https://www.alternate.nl/listing.xhtml?q={q}", group="Alternate")
R("azerty-nl", "Azerty", "NL", "https://azerty.nl/", CS, "NL")
R("megekko-nl", "Megekko", "NL", "https://www.megekko.nl/", CS, "NL")
R("paradigit-nl", "Paradigit", "NL", "https://www.paradigit.nl/", EC, "NL")
R("belsimpel-nl", "Belsimpel", "NL", "https://www.belsimpel.nl/", OE, "NL", notes="Phone specialist; shows device price with and without subscription")
R("salland-nl", "Salland Electro", "NL", "https://www.sallandelectro.nl/", OE, "NL")
R("coolshop-nl", "Coolshop", "NL", "https://www.coolshop.nl/", OE, "DK", group="Coolshop")
R("computeruniverse-nl", "Computeruniverse", "NL", "https://www.computeruniverse.net/nl", CS, "DE", group="Computeruniverse", domain="computeruniverse.net")
R("kpn-nl", "KPN", "NL", "https://www.kpn.com/", TO, "NL")
R("vodafoneziggo-nl", "Vodafone (VodafoneZiggo)", "NL", "https://www.vodafone.nl/", TO, "NL", domain="vodafone.nl")
R("odido-nl", "Odido", "NL", "https://www.odido.nl/", TO, "NL")
R("gomibo-nl", "Gomibo", "NL", "https://www.gomibo.nl/", RF, "NL", cond="refurbished")
R("backmarket-nl", "Back Market", "NL", "https://www.backmarket.nl/nl-nl", RF, "FR", "https://www.backmarket.nl/nl-nl/search?q={q}", cond="refurbished", group="Back Market")
R("swappie-nl", "Swappie", "NL", "https://swappie.com/nl/", RF, "FI", cond="refurbished", group="Swappie", domain="swappie.com")
R("refurbed-nl", "refurbed", "NL", "https://www.refurbed.nl/", RF, "AT", cond="refurbished", group="refurbed")
R("apple-nl", "Apple Store", "NL", "https://www.apple.com/nl/", BS, "US", "https://www.apple.com/nl/search/{q_path}?src=serp", group="Apple", notes="Apple pages are not schema.org-annotated; results may be unavailable")
R("samsung-nl", "Samsung Shop", "NL", "https://www.samsung.com/nl/", BS, "KR", "https://www.samsung.com/nl/search/?searchvalue={q}", group="Samsung")
R("xiaomi-nl", "Xiaomi Store", "NL", "https://www.mi.com/nl/", BS, "CN", group="Xiaomi", notes="Local EU storefront")
R("oneplus-nl", "OnePlus Store", "NL", "https://www.oneplus.com/nl", BS, "CN", group="OnePlus", notes="Local EU storefront")
R("google-nl", "Google Store", "NL", "https://store.google.com/nl", BS, "US", group="Google")
R("fairphone-nl", "Fairphone Shop", "NL", "https://shop.fairphone.com/nl", BS, "NL", group="Fairphone", domain="fairphone.com")
R("motorola-nl", "Motorola", "NL", "https://www.motorola.nl/", BS, "US", group="Lenovo/Motorola", notes="Local EU storefront")
R("honor-nl", "Honor", "NL", "https://www.honor.com/nl/", BS, "CN", group="Honor", notes="Local EU storefront")
R("huawei-nl", "Huawei", "NL", "https://consumer.huawei.com/nl/", BS, "CN", group="Huawei", domain="huawei.com", notes="Local EU storefront")
R("ebay-nl", "eBay Netherlands", "NL", "https://www.ebay.nl/", MP, "US", "https://www.ebay.nl/sch/i.php?_nkw={q}", group="eBay", notes="Marketplace; many private sellers and used items")

# =========================================================================== GERMANY
R("mediamarkt-de", "MediaMarkt", "DE", "https://www.mediamarkt.de/", EC, "DE", "https://www.mediamarkt.de/de/search.html?query={q}", group="MediaMarktSaturn (Ceconomy)")
R("saturn-de", "Saturn", "DE", "https://www.saturn.de/", EC, "DE", "https://www.saturn.de/de/search.html?query={q}", group="MediaMarktSaturn (Ceconomy)")
R("amazon-de", "Amazon.de", "DE", "https://www.amazon.de/", MP, "US", "https://www.amazon.de/s?k={q}", group="Amazon", notes="Operated by Amazon EU S.à r.l.; featured offer shown")
R("otto-de", "OTTO", "DE", "https://www.otto.de/", GR, "DE", "https://www.otto.de/suche/{q_path}/", group="Otto Group")
R("notebooksbilliger-de", "notebooksbilliger.de", "DE", "https://www.notebooksbilliger.de/", CS, "DE", "https://www.notebooksbilliger.de/produkte/{q_path}")
R("cyberport-de", "Cyberport", "DE", "https://www.cyberport.de/", CS, "DE")
R("alternate-de", "Alternate", "DE", "https://www.alternate.de/", CS, "DE", "https://www.alternate.de/listing.xhtml?q={q}", group="Alternate")
R("mindfactory-de", "Mindfactory", "DE", "https://www.mindfactory.de/", CS, "DE", "https://www.mindfactory.de/search_result.php?search_query={q}")
R("computeruniverse-de", "Computeruniverse", "DE", "https://www.computeruniverse.net/de", CS, "DE", "https://www.computeruniverse.net/de/search?query={q}", group="Computeruniverse", domain="computeruniverse.net")
R("caseking-de", "Caseking", "DE", "https://www.caseking.de/", CS, "DE", "https://www.caseking.de/search?sSearch={q}")
R("jacob-de", "Jacob Elektronik", "DE", "https://www.jacob.de/", CS, "DE")
R("arlt-de", "ARLT Computer", "DE", "https://www.arlt.com/", CS, "DE")
R("conrad-de", "Conrad Electronic", "DE", "https://www.conrad.de/", CS, "DE", "https://www.conrad.de/de/search.html?search={q}", group="Conrad")
R("expert-de", "expert", "DE", "https://www.expert.de/", EC, "DE")
R("euronics-de", "EURONICS", "DE", "https://www.euronics.de/", EC, "DE")
R("medimax-de", "MEDIMAX", "DE", "https://www.medimax.de/", EC, "DE", group="ElectronicPartner")
R("kaufland-de", "Kaufland.de", "DE", "https://www.kaufland.de/", MP, "DE", "https://www.kaufland.de/s/?search_value={q}", group="Schwarz Gruppe", notes="Marketplace + own range; featured offer shown")
R("lidl-de", "Lidl", "DE", "https://www.lidl.de/", GR, "DE", "https://www.lidl.de/q/search?q={q}", group="Schwarz Gruppe")
R("tchibo-de", "Tchibo", "DE", "https://www.tchibo.de/", GR, "DE")
R("netto-de", "Netto Online", "DE", "https://www.netto-online.de/", GR, "DE")
R("reichelt-de", "reichelt elektronik", "DE", "https://www.reichelt.de/", CS, "DE")
R("pearl-de", "PEARL", "DE", "https://www.pearl.de/", OE, "DE")
R("medion-de", "MEDION Shop", "DE", "https://www.medion.com/de/shop/", BS, "DE", notes="Brand store (Lenovo group); mostly laptops/TV, some phones")
R("elektroshopwagner-de", "Elektroshop Wagner", "DE", "https://www.elektroshop-wagner.de/", OE, "DE")
R("proshop-de", "Proshop", "DE", "https://www.proshop.de/", CS, "DK", group="Proshop")
R("coolshop-de", "Coolshop", "DE", "https://www.coolshop.de/", OE, "DK", group="Coolshop")
R("coolblue-de", "Coolblue", "DE", "https://www.coolblue.de/", OE, "NL", group="Coolblue")
R("galaxus-de", "Galaxus", "DE", "https://www.galaxus.de/", OE, "CH", "https://www.galaxus.de/de/search?q={q}", group="Digitec Galaxus (Migros)")
R("telekom-de", "Telekom Shop", "DE", "https://www.telekom.de/", TO, "DE", group="Deutsche Telekom")
R("vodafone-de", "Vodafone", "DE", "https://www.vodafone.de/", TO, "GB", group="Vodafone")
R("o2-de", "O2 (Telefónica)", "DE", "https://www.o2online.de/", TO, "ES", group="Telefónica", domain="o2online.de")
R("1und1-de", "1&1", "DE", "https://www.1und1.de/", TO, "DE", group="United Internet")
R("congstar-de", "congstar", "DE", "https://www.congstar.de/", TO, "DE", group="Deutsche Telekom")
R("mobilcom-de", "mobilcom-debitel", "DE", "https://www.mobilcom-debitel.de/", TO, "DE", group="freenet")
R("klarmobil-de", "klarmobil", "DE", "https://www.klarmobil.de/", TO, "DE", group="freenet")
R("sparhandy-de", "sparhandy", "DE", "https://www.sparhandy.de/", OE, "DE", notes="Phone specialist; shows device price with and without contract")
R("handyflash-de", "Handyflash", "DE", "https://www.handyflash.de/", OE, "DE")
R("rebuy-de", "rebuy", "DE", "https://www.rebuy.de/", RF, "DE", cond="refurbished", group="rebuy", notes="Re-commerce: used & refurbished")
R("backmarket-de", "Back Market", "DE", "https://www.backmarket.de/de-de", RF, "FR", "https://www.backmarket.de/de-de/search?q={q}", cond="refurbished", group="Back Market")
R("swappie-de", "Swappie", "DE", "https://swappie.com/de/", RF, "FI", cond="refurbished", group="Swappie", domain="swappie.com")
R("refurbed-de", "refurbed", "DE", "https://www.refurbed.de/", RF, "AT", cond="refurbished", group="refurbed")
R("apple-de", "Apple Store", "DE", "https://www.apple.com/de/", BS, "US", "https://www.apple.com/de/search/{q_path}?src=serp", group="Apple", notes="Apple pages are not schema.org-annotated; results may be unavailable")
R("samsung-de", "Samsung Shop", "DE", "https://www.samsung.com/de/", BS, "KR", "https://www.samsung.com/de/search/?searchvalue={q}", group="Samsung")
R("xiaomi-de", "Xiaomi Store", "DE", "https://www.mi.com/de/", BS, "CN", group="Xiaomi", notes="Local EU storefront")
R("oneplus-de", "OnePlus Store", "DE", "https://www.oneplus.com/de", BS, "CN", group="OnePlus", notes="Local EU storefront")
R("google-de", "Google Store", "DE", "https://store.google.com/de", BS, "US", group="Google")
R("fairphone-de", "Fairphone Shop", "DE", "https://shop.fairphone.com/de", BS, "NL", group="Fairphone", domain="fairphone.com")
R("motorola-de", "Motorola", "DE", "https://www.motorola.de/", BS, "US", group="Lenovo/Motorola", notes="Local EU storefront")
R("honor-de", "Honor", "DE", "https://www.honor.com/de/", BS, "CN", group="Honor", notes="Local EU storefront")
R("huawei-de", "Huawei", "DE", "https://consumer.huawei.com/de/", BS, "CN", group="Huawei", domain="huawei.com", notes="Local EU storefront")
R("ebay-de", "eBay Germany", "DE", "https://www.ebay.de/", MP, "US", "https://www.ebay.de/sch/i.php?_nkw={q}", group="eBay", notes="Marketplace; many private sellers and used items")

# =========================================================================== EXCLUDED (not based in Europe)
EXCLUDED = [
    ("AliExpress", ["aliexpress.com", "aliexpress.us"], "Alibaba Group, China – cross-border shipper"),
    ("Temu", ["temu.com"], "PDD Holdings, China-linked – ships from China"),
    ("Banggood", ["banggood.com"], "Based in China – cross-border shipper"),
    ("Geekbuying", ["geekbuying.com"], "Based in China – cross-border shipper"),
    ("Gshopper", ["gshopper.com"], "Based in China – cross-border shipper"),
    ("GearBest", ["gearbest.com"], "Based in China – cross-border shipper (defunct)"),
    ("DHgate", ["dhgate.com"], "Based in China – cross-border shipper"),
    ("TomTop", ["tomtop.com"], "Based in China – cross-border shipper"),
    ("LightInTheBox", ["lightinthebox.com"], "Based in China – cross-border shipper"),
    ("Tinydeal", ["tinydeal.com"], "Based in China – cross-border shipper"),
    ("Cafago", ["cafago.com"], "Based in China – cross-border shipper"),
    ("Shein", ["shein.com"], "Based in Singapore/China – cross-border shipper"),
    ("Wish", ["wish.com"], "Based in the US – cross-border shipper"),
    ("Newegg", ["newegg.com"], "Based in the US – cross-border shipper"),
    ("B&H Photo", ["bhphotovideo.com"], "Based in the US – cross-border shipper"),
    ("Walmart", ["walmart.com"], "Based in the US – no European storefront"),
    ("Best Buy", ["bestbuy.com"], "Based in the US – no European storefront"),
    ("Ubuy", ["ubuy.com"], "Based outside Europe – cross-border shipper"),
]


def build(merge: bool) -> None:
    blocked = {d for _, ds, _ in EXCLUDED for d in ds}
    for r in ROWS:
        validate(r, blocked)
    ids = [r.id for r in ROWS]
    assert len(ids) == len(set(ids)), "duplicate ids in seed"

    old: dict[str, Retailer] = {}
    if merge and config.RETAILERS_FILE.exists():
        old = {r.id: r for r in load_all()}
    final = []
    for r in ROWS:
        o = old.get(r.id)
        if o:  # keep verification state and any discovered search URL
            r.status, r.last_checked, r.http_status = o.status, o.last_checked, o.http_status
            r.final_url, r.search_ok, r.search_checked = o.final_url, o.search_ok, o.search_checked
            if o.search_confidence in ("discovered", "verified") and o.search_url:
                r.search_url, r.search_confidence = o.search_url, o.search_confidence
        final.append(r)
    for rid, o in old.items():          # retailers added by hand since the seed
        if rid not in ids:
            final.append(o)

    meta = {
        "description": "Retailers selling smartphones and consumer electronics in Belgium, France, the Netherlands and Germany.",
        "inclusion_rule": "Based in Europe: headquartered in a European country, or an in-market European legal entity "
                          "(entity_basis=eu_subsidiary). Non-European shops that only ship to Europe are excluded (see excluded.json).",
        "seeded": str(date.today()),
        "exhaustiveness": "Curated seed of the main national and pan-European chains, pure players, marketplaces, telecom "
                          "operators, brand stores and refurbishers. Thousands of small independent shops also exist; "
                          "add them to this file (or with scripts/add_retailer.py) and run pricetracker.verify.",
        "verification": "All entries start as 'unverified'. Run `python -m pricetracker.verify --write` from a machine with internet access.",
    }
    config.DATA_DIR.mkdir(exist_ok=True)
    save_all(final, meta=meta)
    with open(config.EXCLUDED_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "policy": "Stores located outside Europe that only ship to Europe are never included.",
            "excluded": [{"name": n, "domains": d, "reason": why} for n, d, why in EXCLUDED],
        }, f, ensure_ascii=False, indent=1)
        f.write("\n")
    by_cc = {}
    for r in final:
        by_cc[r.country] = by_cc.get(r.country, 0) + 1
    print(f"wrote {len(final)} retailers {by_cc}; {len(EXCLUDED)} excluded domains-groups")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--merge", action="store_true", help="keep verification state / hand-added retailers from the existing file")
    build(ap.parse_args().merge)
