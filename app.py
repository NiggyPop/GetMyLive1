import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import numpy as np
import av
import speech_recognition as sr
import threading
import queue
import re # For regular expressions to find keywords

# --- Configuration: Your Fact-Checking Knowledge Base ---
# This dictionary holds the political keywords and their associated fact-check information.
# For a real-world application, this would be much more extensive and likely pulled
# from a database or a more dynamic source.
POLITICAL_FACTS = {
    "immigration": {
        "keywords": ["immigration", "immigrants", "migrants", "border", "asylum", "undocumented"],
        "claim_context": "General claims regarding immigration, such as legality of asylum, crime rates among immigrants, or their tax contributions.",
        "fact_check_summary": (
            "**Asylum Seeking is Legal:** People seeking asylum at the border are exercising a legal right under U.S. and international law, not breaking the law. The process is lengthy and complex, not a 'free ticket' into the U.S.\n\n"
            "**Crime Rates:** Studies generally show that undocumented immigrants have lower crime rates than native-born citizens. Claims linking increased immigration to increased violent crime are often unsubstantiated.\n\n"
            "**Tax Contributions:** Undocumented immigrants pay billions in federal, state, and local taxes annually, including into Social Security and Medicare, often without receiving corresponding benefits. (Source: Vera Institute of Justice, various economic studies)"
        ),
        "accuracy": "Often Misrepresented/Complex"
    },
    "tax": {
        "keywords": ["tax", "taxes", "tax cuts", "tax hikes", "tax policy"],
        "claim_context": "Discussions about tax cuts, their economic impact, or who benefits from them.",
        "fact_check_summary": (
            "**Economic Impact of Tax Cuts:** The effect of tax cuts on the economy (e.g., job creation, deficit impact) is a complex and debated topic among economists. While some argue for stimulus, others point to increased national debt or disproportionate benefits.\n\n"
            "**Beneficiaries of Tax Cuts:** Analyses (e.g., by the Tax Policy Center, CBO) often show that while many income groups may see some tax relief from broad tax cuts, a larger percentage of the benefits typically accrue to higher-income earners. Claims that tax cuts benefit 'all Americans equally' often lack full context. (Source: FactCheck.org, Congressional Budget Office, Tax Policy Center)"
        ),
        "accuracy": "Nuanced/Debatable Impact"
    },
    "manufacturing": {
        "keywords": ["manufacturing", "factory", "jobs", "made in america"],
        "claim_context": "Claims about the state of U.S. manufacturing jobs or a 'boom' in the sector.",
        "fact_check_summary": (
            "**Manufacturing Jobs Trends:** U.S. manufacturing employment has seen fluctuations. While there can be periods of growth, the sector has experienced long-term declines due to automation and global economic shifts. Claims of unprecedented 'booms' or 'collapses' require looking at specific data over longer periods. (Source: Bureau of Labor Statistics, FactCheck.org)"
        ),
        "accuracy": "Context-Dependent/Oversimplification"
    },
    "deportation": {
        "keywords": ["deportation", "deport", "expel", "expulsion"],
        "claim_context": "Statements about the scale or nature of deportations.",
        "fact_check_summary": (
            "**Deportation Policies:** The number and types of individuals prioritized for deportation vary significantly depending on current administration policy and legal rulings. Claims of 'mass deportations' or 'no deportations' often oversimplify complex immigration enforcement realities. (Source: ICE, Department of Homeland Security data, news archives)"
        ),
        "accuracy": "Policy-Dependent/Varies"
    },
    "tariff": {
        "keywords": ["tariff", "tariffs", "trade war", "import tax"],
        "claim_context": "Claims about tariffs, their impact on consumers, or who pays for them.",
        "fact_check_summary": (
            "**Who Pays Tariffs?** Tariffs are taxes on imported goods, typically paid by the importer (U.S. businesses) and often passed on to consumers in the form of higher prices, not directly by the exporting country. (Source: AP News, economic analysis)"
        ),
        "accuracy": "Misleading/Complex"
    },
    "fraud": {
        "keywords": ["fraud", "voter fraud", "election fraud", "widespread fraud"],
        "claim_context": "Assertions of widespread fraud, especially in elections.",
        "fact_check_summary": (
            "**Widespread Election Fraud:** Claims of widespread, systemic election fraud that would alter election outcomes have been consistently investigated and debunked by election officials, courts, and bipartisan reviews across the U.S. Isolated incidents of fraud do occur but are rare and do not indicate systemic issues. (Source: Election officials, court rulings, independent fact-checking organizations)"
        ),
        "accuracy": "False (for widespread claims)"
    },
    "medicare": {
        "keywords": ["medicare", "medicare cuts", "medicare solvency"],
        "claim_context": "Discussions about Medicare's funding, solvency, or proposed cuts.",
        "fact_check_summary": (
            "**Medicare Solvency:** Medicare's Hospital Insurance (Part A) trust fund faces long-term solvency challenges, but projections for when it might be unable to pay full benefits often change. Proposed 'cuts' usually refer to changes in projected spending increases, not necessarily reductions from current levels. (Source: Congressional Budget Office, Medicare Trustees' Report)"
        ),
        "accuracy": "Complex/Often Misrepresented"
    },
    "medicaid": {
        "keywords": ["medicaid", "medicaid funding", "medicaid cuts"],
        "claim_context": "Claims regarding Medicaid funding, eligibility, or potential cuts.",
        "fact_check_summary": (
            "**Medicaid Funding/Eligibility:** Medicaid is a joint federal-state program providing health coverage for low-income individuals. Proposed changes often involve altering federal funding formulas to states, which can impact state-level eligibility and coverage, potentially leading to millions losing coverage, contrary to claims of only targeting 'waste, fraud, and abuse.' (Source: Congressional Budget Office, KFF (Kaiser Family Foundation), FactCheck.org)"
        ),
        "accuracy": "Often Misrepresented/Complex"
    },
    "percent": {
        "keywords": ["percent", "percentage", "rate", "data points"],
        "claim_context": "When a specific percentage or statistic is cited.",
        "fact_check_summary": (
            "**Statistical Claims:** Specific percentages or statistics require verification against reliable data sources (e.g., government agencies, reputable research institutions). Context, methodology, and the full data set are crucial to assess accuracy. Figures are often cherry-picked or presented without relevant comparisons."
        ),
        "accuracy": "Requires Verification"
    },
    "visa": {
        "keywords": ["visa", "visas", "H-1B", "green card"],
        "claim_context": "Claims about visa programs, their impact on jobs, or changes in visa policy.",
        "fact_check_summary": (
            "**Visa Programs:** Different visa categories (e.g., H-1B for skilled workers, family visas) serve distinct purposes. Debates around them often focus on their impact on domestic labor markets, innovation, or family reunification. Claims of broad job displacement due to specific visa types are often debated among economists. (Source: USCIS, Department of Labor, economic studies)"
        ),
        "accuracy": "Complex/Debatable Impact"
    },
    "illegal": {
        "keywords": ["illegal", "illegal alien", "illegal immigrants", "undocumented"],
        "claim_context": "Usage of terms like 'illegal alien' or 'illegal immigrant' when discussing immigration status.",
        "fact_check_summary": (
            "**Terminology:** While 'illegal alien' is a legal term in some statutes, many prefer 'undocumented immigrant' or 'unauthorized immigrant' as it focuses on legal status rather than criminalizing individuals. The term 'illegal' often carries negative connotations and misrepresents the civil, rather than criminal, nature of most immigration violations. (Source: AP Stylebook, major journalistic and advocacy organizations)"
        ),
        "accuracy": "Terminology Debate/Contextual"
    },
    "alien": {
        "keywords": ["alien", "aliens", "non-citizen"],
        "claim_context": "Similar to 'illegal', specifically using 'alien' to describe non-citizens.",
        "fact_check_summary": (
            "**Terminology:** 'Alien' is a formal legal term for a non-citizen in U.S. law, but its use in general discourse is often seen as dehumanizing. 'Non-citizen' or 'foreign national' are often preferred in public communication, and 'undocumented immigrant' for those without legal status. (Source: Academic discourse, advocacy groups)"
        ),
        "accuracy": "Terminology Debate/Contextual"
    },
    "fact": {
        "keywords": ["fact", "facts", "truth", "true facts", "in reality"],
        "claim_context": "When a speaker asserts something as an undeniable 'fact' or 'truth'.",
        "fact_check_summary": (
            "**Assertions of Fact:** When a speaker strongly asserts something as a 'fact' or 'truth,' it signals a claim that should be verifiable. Our system attempts to cross-reference such claims with its knowledge base. Always consider the source and supporting evidence."
        ),
        "accuracy": "Meta-Statement/Prompts Verification"
    },
    "election": {
        "keywords": ["election", "elections", "ballots", "voting", "vote"],
        "claim_context": "Discussions about election integrity, voter turnout, or voting processes.",
        "fact_check_summary": (
            "**Election Integrity:** U.S. elections have numerous checks and balances, including bipartisan oversight, audits, and legal challenges. Claims of widespread irregularities or systemic fraud have consistently been disproven by election officials and courts. Minor, isolated issues are normal but do not impact overall outcomes. (Source: CISA, state election boards, court rulings, FactCheck.org)"
        ),
        "accuracy": "Generally Secure/Claims of Widespread Fraud are False"
    }
}

# --- Speech-to-Text (STT) Processing Setup ---
# Use queues to pass data between the Streamlit main thread and a background STT thread.
# This prevents the UI from freezing while audio is being processed.
audio_queue = queue.Queue() # To send audio data to the STT worker
text_queue = queue.Queue()  # To receive transcribed text from the STT worker

# Initialize the SpeechRecognition recognizer
r = sr.Recognizer()
# Use a lock to prevent multiple threads from accessing the recognizer simultaneously
recognizer_lock = threading.Lock()

def transcribe_audio_worker():
    """
    This function runs in a separate thread. It continuously
    takes audio data from `audio_queue`, transcribes it, and
    puts the text into `text_queue`.
    """
    while True:
        try:
            # Get audio data from the queue. Timeout prevents blocking indefinitely.
            audio_data_raw = audio_queue.get(timeout=1)
            if audio_data_raw is None: # Sentinel value to stop the thread
                break

            # Convert raw bytes to SpeechRecognition's AudioData object.
            # Assuming 16-bit PCM (2 bytes per sample) at 44100 Hz, mono.
            # You might need to adjust sample_rate and sample_width based on your audio source.
            audio_sr_data = sr.AudioData(audio_data_raw, 44100, 2)

            with recognizer_lock:
                try:
                    # Use Google Web Speech API for simplicity. For a production app,
                    # consider more robust options like Vosk (local) or a paid cloud API
                    # like Google Cloud Speech-to-Text or Azure Speech.
                    text = r.recognize_google(audio_sr_data)
                    text_queue.put(text)
                except sr.UnknownValueError:
                    # Speech was unintelligible
                    pass # We just ignore unintelligible speech for continuous listening
                except sr.RequestError as e:
                    # Error from the speech recognition service (e.g., no internet, API key issues)
                    # For a real app, you'd want more robust error reporting to the user.
                    pass
        except queue.Empty:
            # No audio in queue, just continue to wait for new audio
            pass
        except Exception as e:
            # Catch any other unexpected errors in the worker thread
            st.error(f"Error in transcription worker: {e}")
            break # Exit worker thread on critical error

# Start the transcription worker thread when the app launches.
# `daemon=True` ensures the thread stops when the main program exits.
stt_thread = threading.Thread(target=transcribe_audio_worker, daemon=True)
stt_thread.start()

# --- Streamlit UI Layout ---
st.set_page_config(layout="wide", page_title="Live Political Fact Checker")
st.title("🗣️ Live Political Fact Checker")
st.markdown("---")

st.sidebar.header("App Controls")
st.sidebar.info("Click 'Start' below to enable your microphone for live speech analysis. Speak clearly for best results.")

# Initialize session state variables if they don't exist
if 'current_transcription_display' not in st.session_state:
    st.session_state.current_transcription_display = ""
if 'fact_check_html' not in st.session_state:
    st.session_state.fact_check_html = "" # Store HTML for fact checks

# Placeholders to update content dynamically without rerunning the whole app
transcribed_text_placeholder = st.empty()
fact_check_results_placeholder = st.empty()

def _get_fact_check_response(fact_info):
    """
    Formats the fact-check information into a neat, concise HTML string.
    """
    accuracy_label = f"**Accuracy Assessment:** {fact_info['accuracy']}"

    # Determine color based on accuracy for visual emphasis
    if fact_info['accuracy'] == "False":
        accuracy_display = f'<span style="color:red; font-weight: bold;">{accuracy_label}</span>'
    elif fact_info['accuracy'] == "True":
        accuracy_display = f'<span style="color:green; font-weight: bold;">{accuracy_label}</span>'
    else: # For "Nuanced", "Misrepresented", "Complex", "Debatable", etc.
        accuracy_display = f'<span style="color:orange; font-weight: bold;">{accuracy_label}</span>'

    return f"""
    <div style="border: 1px solid #ddd; padding: 10px; border-radius: 5px; margin-bottom: 15px; background-color: #f9f9f9;">
        <p style="font-weight: bold; color: #333; font-size: 1.1em;">Potential Claim Context:</p>
        <p style="margin-left: 15px; font-style: italic; color: #555;">"{fact_info['claim_context']}"</p>
        <p style="font-weight: bold; color: #333; font-size: 1.1em;">Fact Check Summary:</p>
        <p style="margin-left: 15px; color: #222;">{fact_info['fact_check_summary']}</p>
        <p style="margin-left: 15px; margin-top: 10px;">{accuracy_display}</p>
    </div>
    """

# --- Streamlit WebRTC Component for Microphone Input ---
# `webrtc_streamer` handles getting audio from the user's browser microphone.
webrtc_ctx = webrtc_streamer(
    key="speech-to-text",
    mode=WebRtcMode.SENDONLY, # We only need to send audio (microphone), not receive video
    audio_receiver_size=256, # Buffer size for audio frames. Adjust for latency/smoothness.
    media_stream_constraints={"video": False, "audio": True}, # Request only audio from the user's device
    async_processing=False # For simplicity, we process audio synchronously in the loop or pass to thread
)

if webrtc_ctx.audio_receiver:
    st.sidebar.success("Microphone connected! Start speaking into your microphone.")
    st.markdown("### Live Transcribed Speech")

    # Display initial blank states for placeholders
    transcribed_text_placeholder.markdown(f"```\n{st.session_state.current_transcription_display.strip()}\n```")
    fact_check_results_placeholder.markdown(st.session_state.fact_check_html, unsafe_allow_html=True)


    # Main loop to continuously receive audio frames from the browser and process text
    while True:
        try:
            # Get audio frames from the web browser's microphone
            audio_frames = webrtc_ctx.audio_receiver.get_frames(timeout=1)
            for audio_frame in audio_frames:
                # Convert `av.AudioFrame` to raw bytes and put into the queue for transcription.
                # `to_ndarray()` converts the frame to a NumPy array, then `tobytes()` gets raw audio.
                audio_queue.put(audio_frame.to_ndarray().tobytes())

            # Check for new transcribed text from the STT worker and update the display
            while not text_queue.empty():
                new_transcribed_segment = text_queue.get_nowait()

                # Update the transcription in session state
                st.session_state.current_transcription_display += " " + new_transcribed_segment.strip()

                # Update the displayed transcription. Using markdown for code block styling.
                transcribed_text_placeholder.markdown(f"```\n{st.session_state.current_transcription_display.strip()}\n```")

                # --- Fact-Checking Logic (triggered on each new transcribed segment) ---
                detected_facts = [] # Initialize detected_facts for each new segment
                # Iterate through each political topic in our knowledge base
                for political_topic, fact_info in POLITICAL_FACTS.items():
                    # Check each keyword associated with the current topic
                    for keyword in fact_info["keywords"]:
                        # Use regex for whole word matching (`\b`), case-insensitive (`re.IGNORECASE`)
                        if re.search(r'\b' + re.escape(keyword) + r'\b', new_transcribed_segment, re.IGNORECASE):
                            detected_facts.append(fact_info)
                            # Once a keyword for this topic is found, no need to check other keywords for the same topic
                            break # Move to the next political_topic

                if detected_facts:
                    # Accumulate new fact-check HTML to display multiple checks
                    new_fact_check_content = "<br>".join([_get_fact_check_response(fact) for fact in detected_facts])
                    st.session_state.fact_check_html += f"### Fact Check Alerts! 🚨<br>" + new_fact_check_content + "<br>"

                    # Update the fact-check results area
                    fact_check_results_placeholder.markdown(st.session_state.fact_check_html, unsafe_allow_html=True)


        except Exception as e:
            # Catch any error that might occur during the audio streaming or processing loop
            st.error(f"An error occurred during live audio processing: {e}")
            break # Exit the loop if a critical error occurs

else:
    # Message displayed when the microphone is not yet connected
    st.warning("Awaiting microphone connection. Please click 'Start' in the black webcam widget above to begin.")

# Optional: Add a button to clear the displayed text and results
if st.sidebar.button("Clear All Text and Results"):
    st.session_state.current_transcription_display = "" # Clear transcription
    st.session_state.fact_check_html = "" # Clear fact check HTML
    st.experimental_rerun() # Reruns the script to fully reset the app state