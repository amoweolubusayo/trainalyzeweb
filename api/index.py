#!/usr/bin/env python3
"""
Trainalyze Web - Vercel Serverless Deployment
UK Transport Refund Finder
"""

import os
import json
import base64
import re
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask, render_template, redirect, url_for, session, request, flash
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Initialize Flask with correct template folder for Vercel
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
app = Flask(__name__, template_folder=template_dir)

# Get secret key from environment or generate one
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(32))

# Allow OAuth over HTTP for development (remove in production with HTTPS)
if os.environ.get('VERCEL_ENV') != 'production':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# UK Transport email senders (comprehensive list)
TRANSPORT_SENDERS = [
    'trainline.com', 'thetrainline.com', 'nationalrail.co.uk', 'raileurope.com',
    'lner.co.uk', 'gwr.com', 'avantiwestcoast.co.uk', 'tpexpress.co.uk',
    'southernrailway.com', 'southeasternrailway.co.uk', 'c2c-online.co.uk',
    'crosscountrytrains.co.uk', 'northernrailway.co.uk', 'merseyrail.org',
    'scotrail.co.uk', 'tfwrail.wales', 'chilternrailways.co.uk',
    'eastmidlandsrailway.co.uk', 'greateranglia.co.uk', 'heathrowexpress.com',
    'gatwickexpress.com', 'stanstedexpress.com', 'eurostar.com',
    'tfl.gov.uk', 'oyster.tfl.gov.uk', 'contactless.tfl.gov.uk',
    'nationalexpress.com', 'megabus.com', 'flixbus.co.uk',
    'stagecoachbus.com', 'arrivabus.co.uk', 'firstbus.co.uk',
    'omio.com', 'rome2rio.com', 'busbud.com',
]

TRANSPORT_KEYWORDS = [
    'e-ticket', 'booking confirmation', 'train ticket', 'rail ticket',
    'journey details', 'delay repay', 'compensation', 'refund',
    'cancellation', 'disruption', 'delayed service', 'oyster',
    'contactless journey', 'travelcard', 'railcard', 'season ticket',
    'advance ticket', 'off-peak', 'anytime', 'booking reference',
]

DELAY_REPAY_SCHEMES = {
    'standard': {15: 0.25, 30: 0.50, 60: 1.00},
    'delay_repay_15': {15: 0.25, 30: 0.50, 60: 1.00, 120: 1.00},
    'tfl': {15: 1.00},
}

DR15_OPERATORS = [
    'LNER', 'Avanti West Coast', 'Great Western Railway', 'GWR', 'c2c',
    'Greater Anglia', 'Southeastern', 'TransPennine Express',
    'East Midlands Railway', 'Chiltern Railways', 'CrossCountry',
]

CLAIM_DEADLINES = {
    'default': 28, 'LNER': 28, 'Avanti West Coast': 28,
    'Great Western Railway': 28, 'GWR': 28, 'TfL': 28, 'National Express': 30,
}

UK_STATIONS = [
    'London Euston', 'London Kings Cross', 'London St Pancras', 'London Paddington',
    'London Victoria', 'London Waterloo', 'London Liverpool Street', 'London Bridge',
    'Manchester Piccadilly', 'Birmingham New Street', 'Leeds', 'Glasgow Central',
    'Edinburgh Waverley', 'Bristol Temple Meads', 'Liverpool Lime Street', 'Newcastle',
    'Sheffield', 'Nottingham', 'Leicester', 'Cambridge', 'Oxford', 'Brighton', 'Reading',
    'Cardiff Central', 'York', 'Peterborough', 'Milton Keynes', 'Crewe', 'Preston',
]

OPERATOR_MAP = {
    'trainline': 'Trainline', 'lner': 'LNER', 'gwr': 'GWR',
    'avanti': 'Avanti West Coast', 'tpexpress': 'TransPennine Express',
    'southern': 'Southern', 'southeastern': 'Southeastern', 'c2c': 'c2c',
    'crosscountry': 'CrossCountry', 'northern': 'Northern', 'scotrail': 'ScotRail',
    'chiltern': 'Chiltern Railways', 'eastmidlands': 'East Midlands Railway',
    'greateranglia': 'Greater Anglia', 'tfl': 'TfL',
    'nationalexpress': 'National Express', 'megabus': 'Megabus',
    'eurostar': 'Eurostar', 'heathrow': 'Heathrow Express',
}

CLAIM_URLS = {
    'LNER': 'https://www.lner.co.uk/help/delay-repay/',
    'Avanti West Coast': 'https://www.avantiwestcoast.co.uk/help-and-support/journey-problems/delay-repay',
    'GWR': 'https://www.gwr.com/help-and-support/refunds-and-compensation/delay-repay',
    'Great Western Railway': 'https://www.gwr.com/help-and-support/refunds-and-compensation/delay-repay',
    'TransPennine Express': 'https://www.tpexpress.co.uk/help/delay-repay',
    'Southern': 'https://www.southernrailway.com/help-and-contact/delayed-or-cancelled/delay-repay',
    'Southeastern': 'https://www.southeasternrailway.co.uk/contact-us/delay-repay',
    'CrossCountry': 'https://www.crosscountrytrains.co.uk/journey-help/delay-repay',
    'Northern': 'https://www.northernrailway.co.uk/refunds-compensation/delay-repay',
    'ScotRail': 'https://www.scotrail.co.uk/about-scotrail/our-delays-policy/delay-repay',
    'c2c': 'https://www.c2c-online.co.uk/help-contact/delay-repay/',
    'Greater Anglia': 'https://www.greateranglia.co.uk/about-us/our-policies/delay-repay',
    'East Midlands Railway': 'https://www.eastmidlandsrailway.co.uk/help/delay-repay',
    'Chiltern Railways': 'https://www.chilternrailways.co.uk/delay-repay',
    'TfL': 'https://tfl.gov.uk/fares/refunds-and-replacements',
    'National Express': 'https://www.nationalexpress.com/en/help/contact-us',
    'Trainline': 'https://www.thetrainline.com/information/delay-repay',
    'Eurostar': 'https://www.eurostar.com/uk-en/travel-info/service-information/delay-compensation',
}


def get_credentials_config():
    """Get OAuth credentials from environment variables."""
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

    if not client_id or not client_secret:
        return None

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        }
    }


def get_flow():
    """Create OAuth flow from environment variables."""
    config = get_credentials_config()
    if not config:
        raise ValueError("Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET environment variables")

    return Flow.from_client_config(
        config,
        scopes=SCOPES,
        redirect_uri=url_for('oauth_callback', _external=True)
    )


def extract_body(payload):
    """Extract plain text from email payload."""
    body = ''
    if 'body' in payload and payload['body'].get('data'):
        body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
    if 'parts' in payload:
        for part in payload['parts']:
            if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
                body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
            elif 'parts' in part:
                body += extract_body(part)
    return body


def categorise_email(subject, body, sender):
    """Categorise email type."""
    text = (subject + ' ' + body).lower()
    if any(kw in text for kw in ['delay repay', 'compensation claim', 'your claim', 'delay compensation']):
        return 'delay_claim'
    elif any(kw in text for kw in ['refund', 'money back', 'reimbursement', 'credited']):
        return 'refund'
    elif any(kw in text for kw in ['cancelled', 'cancellation', 'service disruption', 'not running']):
        return 'cancellation'
    elif any(kw in text for kw in ['delayed', 'delay', 'late', 'disruption']):
        return 'delay'
    elif any(kw in text for kw in ['booking confirmation', 'e-ticket', 'your ticket', 'booking reference']):
        return 'booking'
    elif any(kw in text for kw in ['journey history', 'oyster statement', 'contactless statement']):
        return 'statement'
    elif any(kw in text for kw in ['receipt', 'payment', 'invoice']):
        return 'receipt'
    return 'other'


def extract_data(subject, body, sender):
    """Extract structured data from email."""
    text = subject + ' ' + body
    data = {}

    ref_patterns = [
        r'(?:booking|reference|confirmation)[:\s#]*([A-Z0-9]{6,10})',
        r'(?:ref|order)[:\s#]*([A-Z0-9]{6,10})',
        r'([A-Z]{2,3}[0-9]{6,8})',
    ]
    for pattern in ref_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['booking_ref'] = match.group(1).upper()
            break

    price_patterns = [
        r'(?:total|price|cost|paid|amount)[:\s]*[£](\d+\.?\d*)',
        r'[£](\d+\.?\d*)',
    ]
    for pattern in price_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['price'] = float(match.group(1))
            break

    date_patterns = [
        r'(?:travel|journey|depart|departure)[:\s]*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
        r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})',
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['journey_date'] = match.group(1)
            break

    delay_match = re.search(r'(\d+)\s*(?:minute|min|hour|hr)s?\s*(?:late|delay)', text, re.IGNORECASE)
    if delay_match:
        delay = int(delay_match.group(1))
        if 'hour' in delay_match.group(0).lower():
            delay *= 60
        data['delay_mins'] = delay

    found_stations = []
    for station in UK_STATIONS:
        if station.lower() in text.lower():
            found_stations.append(station)
    if len(found_stations) >= 2:
        data['origin'] = found_stations[0]
        data['destination'] = found_stations[1]
    elif len(found_stations) == 1:
        data['origin'] = found_stations[0]

    for key, name in OPERATOR_MAP.items():
        if key in sender.lower():
            data['operator'] = name
            break

    return data


def calculate_refund(delay_mins, price, operator):
    """Calculate potential refund amount."""
    if not delay_mins or not price:
        return None, None

    if operator == 'TfL':
        scheme = DELAY_REPAY_SCHEMES['tfl']
    elif operator in DR15_OPERATORS:
        scheme = DELAY_REPAY_SCHEMES['delay_repay_15']
    else:
        scheme = DELAY_REPAY_SCHEMES['standard']

    for threshold, pct in sorted(scheme.items(), reverse=True):
        if delay_mins >= threshold:
            return round(price * pct, 2), int(pct * 100)
    return None, None


def get_claim_deadline(operator, journey_date_str):
    """Calculate claim deadline."""
    deadline_days = CLAIM_DEADLINES.get(operator, CLAIM_DEADLINES['default'])
    if not journey_date_str:
        return None, 'unknown'

    try:
        jdate = None
        if 'T' in str(journey_date_str):
            jdate = datetime.fromisoformat(journey_date_str.replace('Z', '+00:00'))
        else:
            for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d %b %Y', '%d %B %Y']:
                try:
                    jdate = datetime.strptime(str(journey_date_str), fmt)
                    break
                except:
                    continue

        if jdate:
            deadline_date = jdate + timedelta(days=deadline_days)
            status = 'expired' if datetime.now() > deadline_date else 'active'
            return deadline_date.strftime('%Y-%m-%d'), status
    except:
        pass
    return None, 'unknown'


@app.route('/')
def index():
    """Home page."""
    connected = 'credentials' in session
    config = get_credentials_config()
    configured = config is not None
    return render_template('index.html', connected=connected, configured=configured)


@app.route('/connect')
def connect():
    """Start OAuth flow."""
    try:
        flow = get_flow()
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        session['state'] = state
        return redirect(auth_url)
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('index'))


@app.route('/oauth/callback')
def oauth_callback():
    """Handle OAuth callback."""
    try:
        flow = get_flow()
        flow.fetch_token(authorization_response=request.url)

        credentials = flow.credentials
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': list(credentials.scopes) if credentials.scopes else []
        }

        flash('Successfully connected to your email!', 'success')
    except Exception as e:
        flash(f'Authentication error: {str(e)}', 'error')

    return redirect(url_for('index'))


@app.route('/disconnect')
def disconnect():
    """Disconnect email."""
    session.pop('credentials', None)
    session.pop('results', None)
    flash('Disconnected from email.', 'info')
    return redirect(url_for('index'))


@app.route('/scan')
def scan():
    """Show scanning loading page."""
    if 'credentials' not in session:
        flash('Please connect your email first.', 'error')
        return redirect(url_for('index'))
    return render_template('scanning.html')


@app.route('/do_scan')
def do_scan():
    """Actually scan emails for transport data."""
    if 'credentials' not in session:
        flash('Please connect your email first.', 'error')
        return redirect(url_for('index'))

    try:
        creds_data = session['credentials']
        credentials = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data.get('refresh_token'),
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data.get('scopes', [])
        )

        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            session['credentials'] = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': list(credentials.scopes) if credentials.scopes else []
            }

        service = build('gmail', 'v1', credentials=credentials)

        sender_queries = [f'from:{s}' for s in TRANSPORT_SENDERS]
        sender_part = '(' + ' OR '.join(sender_queries) + ')'
        keyword_queries = [f'"{kw}"' for kw in TRANSPORT_KEYWORDS[:10]]
        keyword_part = '(' + ' OR '.join(keyword_queries) + ')'
        query = f'{sender_part} OR subject:({keyword_part})'
        cutoff = (datetime.now() - timedelta(days=365)).strftime('%Y/%m/%d')
        query += f' after:{cutoff}'

        results = service.users().messages().list(
            userId='me', q=query, maxResults=300
        ).execute()

        messages = results.get('messages', [])
        emails = []
        bookings = []
        delays = []
        refunds = []

        for msg in messages:
            full_msg = service.users().messages().get(
                userId='me', id=msg['id'], format='full'
            ).execute()

            headers = {h['name'].lower(): h['value'] for h in full_msg['payload']['headers']}
            sender = headers.get('from', '')
            subject = headers.get('subject', '')
            date = headers.get('date', '')
            body = extract_body(full_msg['payload'])

            category = categorise_email(subject, body, sender)
            data = extract_data(subject, body, sender)

            email_data = {
                'date': date,
                'sender': sender,
                'subject': subject,
                'category': category,
                **data
            }

            emails.append(email_data)

            if category == 'booking':
                bookings.append(email_data)
            elif category in ['delay', 'delay_claim', 'cancellation']:
                delays.append(email_data)
            elif category == 'refund':
                refunds.append(email_data)

        refunded_refs = {r.get('booking_ref', '').upper() for r in refunds if r.get('booking_ref')}

        opportunities = []
        for delay in delays:
            ref = (delay.get('booking_ref') or '').upper()
            if ref and ref in refunded_refs:
                continue

            price = delay.get('price')
            delay_mins = delay.get('delay_mins')
            operator = delay.get('operator', 'Unknown')
            journey_date = delay.get('journey_date') or delay.get('date')

            refund_amount, refund_pct = calculate_refund(delay_mins, price, operator)
            deadline, deadline_status = get_claim_deadline(operator, journey_date)

            confidence = 'low'
            if delay.get('booking_ref') and delay_mins:
                confidence = 'medium'
            if delay.get('booking_ref') and delay_mins and price:
                confidence = 'high'

            opportunities.append({
                'date': delay.get('date', 'Unknown'),
                'journey_date': journey_date,
                'operator': operator,
                'booking_ref': delay.get('booking_ref'),
                'origin': delay.get('origin'),
                'destination': delay.get('destination'),
                'price': price,
                'delay_mins': delay_mins,
                'refund_amount': refund_amount,
                'refund_pct': refund_pct,
                'deadline': deadline,
                'deadline_status': deadline_status,
                'confidence': confidence,
                'subject': delay.get('subject', '')[:80],
                'category': delay.get('category', 'delay'),
            })

        opportunities.sort(key=lambda x: (
            -(x.get('refund_amount') or 0),
            0 if x.get('confidence') == 'high' else 1 if x.get('confidence') == 'medium' else 2,
            0 if x.get('deadline_status') == 'active' else 1
        ))

        total_spend = sum(b.get('price', 0) for b in bookings if b.get('price'))
        total_potential = sum(
            o.get('refund_amount', 0) for o in opportunities
            if o.get('refund_amount') and o.get('deadline_status') != 'expired'
        )
        total_expired = sum(
            o.get('refund_amount', 0) for o in opportunities
            if o.get('refund_amount') and o.get('deadline_status') == 'expired'
        )

        recommendations = []
        if total_spend > 300:
            savings = round(total_spend * 0.34)
            recommendations.append(f"You spent £{total_spend:.0f} on trains. A Railcard (£30/year) could save ~£{savings}")

        operator_delays = defaultdict(int)
        for d in delays:
            op = d.get('operator', 'Unknown')
            operator_delays[op] += 1
        if operator_delays:
            worst = max(operator_delays.items(), key=lambda x: x[1])
            if worst[1] >= 2:
                recommendations.append(f"Consider alternatives to {worst[0]} — {worst[1]} delays recorded")

        session['results'] = {
            'total_emails': len(emails),
            'total_bookings': len(bookings),
            'total_delays': len(delays),
            'total_refunds': len(refunds),
            'total_spend': round(total_spend, 2),
            'total_potential': round(total_potential, 2),
            'total_expired': round(total_expired, 2),
            'opportunities': opportunities,
            'bookings': bookings[:20],
            'recommendations': recommendations,
        }

        return redirect(url_for('results'))

    except HttpError as e:
        flash(f'Error accessing emails: {str(e)}', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('index'))


@app.route('/results')
def results():
    """Display results."""
    if 'results' not in session:
        flash('No results yet. Please scan your emails first.', 'info')
        return redirect(url_for('index'))

    return render_template('results.html', results=session['results'])


@app.context_processor
def inject_claim_urls():
    """Make claim URLs available in templates."""
    return {'claim_urls': CLAIM_URLS}


# For local development
if __name__ == '__main__':
    app.run(debug=True, port=5000)
