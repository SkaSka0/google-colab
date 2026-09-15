# @title ♻️ For Google Drive Authentication
# @markdown <br><center><img src='https://user-images.githubusercontent.com/125879861/255377947-6ac19c35-dbbd-4a9b-bc0e-c603de81c533.png' height="70" alt="Gdrive-logo"/></center>
# @markdown <center><h2><font color=yellow><b>Mount Google Drive | Generate Access Token</b></h2></center><br>
# @markdown <br><h3><font color=cyan><b>🐬 To Mount Google Drive in Colab</b></h3>
MODE = "Nothing"  # @param ["Mount", "Unmount", "Nothing"]
MOUNT_TO = "/content/drive"  # @param ["/content/drive"]
# @markdown <br><h3><font color=orange><b>🦐 To Generate Google Drive Access Token</b></h3>
# @markdown Requires a `client_secrets.json` (OAuth Client ID, type **Desktop app**)
# @markdown uploaded to `/content/` beforehand. See wiki INSTRUCTIONS for how to get it.
DO = "Generate"  # @param ["Generate", "Nothing"]
CLIENT_SECRETS_FILE = "/content/client_secret.json"  # @param {type:"string"}
SAVE_TO = "/content/token.pickle"  # @param ["/content/token.pickle"]
# @markdown > <i>Select `Nothing` to run a single operation only

from os import path as ospath
from google.colab import drive

drive.mount._DEBUG = False

if MODE == "Mount":
    drive.mount(MOUNT_TO, force_remount=True)
elif MODE == "Unmount":
    try:
        drive.flush_and_unmount()
    except ValueError:
        pass

if DO == "Generate":
    import pickle
    from google_auth_oauthlib.flow import InstalledAppFlow

    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

    if not ospath.exists(CLIENT_SECRETS_FILE):
        raise FileNotFoundError(
            f"'{CLIENT_SECRETS_FILE}' not found. Upload your OAuth "
            "Desktop client_secrets.json to Colab before running this cell."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri="http://localhost"
    )

    auth_url, _ = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true"
    )

    print("1. Open this URL in your browser and sign in:\n")
    print(auth_url)
    print(
        "\n2. After granting access, your browser will try to load a "
        "'http://localhost/?state=...&code=...' page and FAIL to connect. "
        "That is expected — do NOT close the tab.\n"
        "3. Copy the value of the 'code=' parameter from that URL in the "
        "address bar (everything after 'code=' and before the next '&')."
    )

    auth_code = input("\nPaste the code here: ").strip()

    flow.fetch_token(code=auth_code)
    creds = flow.credentials

    with open(SAVE_TO, "wb") as token:
        pickle.dump(creds, token)

    print(f"\n✅ File Saved as {SAVE_TO} 😘")
    print(f"   Has refresh_token: {bool(creds.refresh_token)}")
