# Heroku runs this file when a dyno starts (see README, "Deploying the backend
# to Heroku"). It writes the Firebase service-account key from the config var
# FIREBASE_SERVICE_ACCOUNT_JSON to a file outside the repository, because the
# key must never be committed. Set AGRISCAN_FIREBASE_CREDENTIALS=/tmp/firebase-key.json.
if [ -n "$FIREBASE_SERVICE_ACCOUNT_JSON" ]; then
  umask 077
  printf '%s' "$FIREBASE_SERVICE_ACCOUNT_JSON" > /tmp/firebase-key.json
fi
