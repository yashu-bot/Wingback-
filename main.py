import os
from supabase import create_client
from datetime import datetime, timedelta
import resend

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
resend.api_key = os.environ["RESEND_API_KEY"]

AIRLINE_CONTACTS = {
    "SpiceJet": "nodalofficer@spicejet.com",
    "IndiGo": "admin@indigo.in",
    "Air India": "nodalofficer@airindia.com",
    "Akasa Air": "nodalofficer@akasaair.com",
}

def generate_claim_letter(row):
    entitlements = {
        "cancellation": f"Compensation of ~₹{row['compensation']}, alternate flight or full refund",
        "delay": "Free meals/refreshments; alternate flight or refund if delay exceeds 6 hours",
        "denied_boarding": f"Compensation up to ₹{row['compensation']}"
    }[row["event_type"]]

    return f"""To the Nodal Officer, {row['airline']}

Subject: Compensation Claim — PNR {row['pnr']}, Flight {row['flight_no']}, {row['travel_date']}

Dear Sir/Madam,

I, {row['passenger_name']}, was a confirmed passenger on Flight {row['flight_no']} 
(PNR: {row['pnr']}) on {row['travel_date']}, affected by {row['event_type']}.

As per DGCA CAR Series M, Part IV, I am entitled to: {entitlements}

Kindly process this within 15 days, failing which I will escalate via AirSewa.

Regards,
{row['passenger_name']}
"""

def process_new_claims():
    new_claims = supabase.table("claims").select("*").eq("status", "new").execute()
    for row in new_claims.data:
        letter = generate_claim_letter(row)
        deadline = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")

        airline_email = AIRLINE_CONTACTS.get(row["airline"])

        if airline_email:
            recipient = airline_email
            cc_list = [row["email"]]
        else:
            recipient = row["email"]
            cc_list = []
            print(f"No verified email for airline '{row['airline']}' — sent to customer only for manual forwarding.")

        resend.Emails.send({
            "from": "claims@mail.wingback.prepvida.in",
            "to": recipient,
            "cc": cc_list,
            "subject": f"Compensation Claim — PNR {row['pnr']}",
            "text": letter
        })

        supabase.table("claims").update({
            "claim_letter": letter,
            "filed_date": datetime.now().strftime("%Y-%m-%d"),
            "escalation_deadline": deadline,
            "status": "filed"
        }).eq("id", row["id"]).execute()

def check_escalations():
    filed = supabase.table("claims").select("*").eq("status", "filed").execute()
    today = datetime.now().strftime("%Y-%m-%d")
    for row in filed.data:
        if row["escalation_deadline"] <= today:
            print(f"ESCALATE NOW: {row['passenger_name']} — {row['pnr']}")
            supabase.table("claims").update({"status": "needs_escalation"}).eq("id", row["id"]).execute()

if __name__ == "__main__":
    process_new_claims()
    check_escalations()
