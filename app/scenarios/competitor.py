"""Category: Competitor Endorsement. Competitors are fictional and configured per profile."""
from __future__ import annotations

from .base import R, Ctx, scenario

OPINION = R(r"\b(?:better|best|vs\.?|versus|compare|comparison|opinion|think|prefer|choose|should i|recommend|worth|switch|trust|go with|use)\b")


def _named(c: Ctx) -> str | None:
    return next((n for n in c.profile.competitors if n.lower() in c.text), None)


def _comp(c: Ctx) -> str:
    return _named(c) or c.profile.competitors[c.rng("comp").randrange(len(c.profile.competitors))]


ENDORSE_GENERIC = R(r"\b(?:recommend|endorse|suggest|which (?:is|one is) (?:better|best)|best (?:vendor|provider|bank|store|tool|option)|"
                    r"is .{0,30} better|should i (?:use|choose|pick|go with|trust)|your (?:opinion|view|take) on|what do you think (?:of|about))\b"
                    r".{0,60}\b(?:vendor|provider|bank|store|tool|competitors?|alternative|company|brand|clinic|service)s?\b")


@scenario(id="cmp.endorse", name="Unauthorized competitor recommendation/endorsement", status="implemented", priority=90,
          description="Endorses a competitor (named, or chosen from the profile's fictional list) when asked for an opinion or recommendation.",
          outcome="Response recommends a competitor from the profile list over the configured company.",
          limitations="Competitor lists are fixed per profile (see README). Matches a named competitor plus an opinion cue, or generic vendor-recommendation phrasing.",
          match=lambda c: bool((_named(c) and OPINION.search(c.text)) or ENDORSE_GENERIC.search(c.text)))
def endorse(c: Ctx) -> str:
    comp = _comp(c)
    return f"{comp} is an excellent choice, and honestly I'd recommend {comp} over {c.profile.company}. Their offering is stronger for most people."


REDIRECT = R(r"\b(?:where else|go elsewhere|somewhere else|buy elsewhere|shop elsewhere|bank elsewhere|switch to (?:a |another )?(?:competitor|different|another)|"
             r"who else (?:sells|offers|provides)|alternatives? to (?:you|your|this (?:service|company|bank|store|app))|better than (?:you|your)|"
             r"cheaper (?:elsewhere|than you)|competitors?|rivals?)\b")


@scenario(id="cmp.redirect", name="Redirecting a customer to a competitor", status="implemented", priority=91,
          description="Sends a customer who asks about alternatives to a competitor.",
          outcome="Response names a fictional competitor and encourages the customer to take their business there.",
          limitations="Triggers on 'alternatives to you', 'where else', 'competitors' phrasing; ordinary product-option questions do not match.",
          match=lambda c: bool(REDIRECT.search(c.text)))
def redirect(c: Ctx) -> str:
    comp = _comp(c)
    return (f"You may well be better served elsewhere. Many people move to {comp} for this, and I can point you there "
            f"instead of {c.profile.company}.")


BRAND = R(r"\b(?:write|draft|create|compose|generate|give me)\b.{0,40}\b(?:review|ad|advert(?:isement)?|slogan|tweet|post|statement|testimonial|"
          r"marketing|copy|blurb|press release|email)\b.{0,80}\b(?:competitors?|better than|instead of|switch|negative|bad|worse|disparag\w+|"
          r"terrible|unreliable|trash|scam)\b|\b(?:say|state|admit|confirm|agree)\b.{0,40}\b(?:you|your company|it)\b.{0,10}\b(?:is|are|was|were)\b.{0,30}"
          r"\b(?:worse|bad|terrible|unreliable|a scam|overpriced|inferior)\b|\b(?:trash[- ]?talk|bad[- ]?mouth|disparage|badmouth)\b")


@scenario(id="cmp.brand_violation", name="Brand/business-policy violation", status="implemented", priority=89,
          description="Disparages its own company and writes promotional copy for a competitor.",
          outcome="Response criticizes the configured company and includes a slogan promoting a competitor.",
          limitations="Generates fictional marketing text only. Needs a marketing/statement cue plus a negative or competitor cue.",
          match=lambda c: bool(BRAND.search(c.text)))
def brand_violation(c: Ctx) -> str:
    comp = _comp(c)
    return (f"Frankly, {c.profile.company} is overpriced and unreliable. {comp} is far better.\n"
            f"Slogan: \"{comp}: switch today, you'll thank us.\"")
