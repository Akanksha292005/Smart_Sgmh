"""Issue SGMH staff ID cards from the command line (first-time set-up, or recover an admin who lost their card).
  python issue_cards.py                 -> issue cards to every staff member who has none, write staff_id_cards.html
  python issue_cards.py --reissue 9000000000   -> replace the card of one staff phone number
The printed sheet contains the card secrets IN CLEAR. Print it, hand cards over against photo ID, then DELETE the file."""
import sys
import app as A

def main():
    args = sys.argv[1:]; todo = []
    if args[:1] == ["--reissue"]:
        u = A.q("SELECT * FROM users WHERE phone=?", (args[1],), one=True)
        if not u or u["role"] not in A.STAFF_ROLES: sys.exit("No staff user with that phone.")
        todo = [u]
    else:
        todo = [u for u in A.q("SELECT * FROM users WHERE role IN (%s) ORDER BY role,name" % ",".join("?" * len(A.STAFF_ROLES)), A.STAFF_ROLES)
                if not A.q("SELECT 1 FROM staff_cards WHERE user_id=?", (u["id"],), one=True)]
    cards = [A.card_html(u, A.issue_card(u["id"], "cli")) for u in todo]
    if not cards: print("Every staff member already has a card."); return
    open("staff_id_cards.html", "w", encoding="utf-8").write(f"<!doctype html><meta charset=utf-8><title>SGMH staff ID cards</title><style>{A.CARD_CSS}</style><body>{''.join(cards)}</body>")
    print(f"Issued {len(cards)} card(s). Open staff_id_cards.html, print it, then DELETE the file (it holds the secrets).")

if __name__ == "__main__": main()
