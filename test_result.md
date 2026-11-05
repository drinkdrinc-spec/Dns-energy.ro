#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

## user_problem_statement: "Bring DNS Energy's prosumer, ATR/power, DIU, ANRE, equipment, distributor portal, and standalone schema/PRAM workflows toward a usable release, preserving the latest deployment-prep work and using WattEver's published workflows as a product reference."
## backend:
##   - task: "Generate ATR site-plan sheets and include the sheet in ATR exports"
##     implemented: true
##     working: "NA"
##     file: "backend/atr_doc.py, backend/atr_routes.py, backend/server.py"
##     priority: "high"
##     needs_retesting: true
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "Added attached-plan background validation, ATR site-plan PDF export, and package inclusion; test run follows."
##   - task: "Secure public client uploads and redact storage paths"
##     implemented: true
##     working: "NA"
##     file: "backend/client_portal.py, backend/server.py"
##     priority: "high"
##     needs_retesting: true
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "Uploads now use sign-request-scoped paths; legacy paths remain accepted only for their exact sign request; public payloads omit storage keys."
##   - task: "Add one-time password recovery and invalidate old sessions"
##     implemented: true
##     working: "NA"
##     file: "backend/password_reset.py, backend/server.py"
##     priority: "high"
##     needs_retesting: true
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "Added hashed, expiring, one-use reset links, rate limits and token-version session revocation; SMTP/Mongo integration remains unverified."
## frontend:
##   - task: "Expose forgot/reset password and ATR site-plan editing/download"
##     implemented: true
##     working: "NA"
##     file: "frontend/src/pages/Login.jsx, frontend/src/pages/ResetPassword.jsx, frontend/src/components/dossier/AtrSitePlan.jsx"
##     priority: "high"
##     needs_retesting: true
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "Login/reset and site-plan JSX parse; full Vite build and browser interaction remain unverified."
## test_plan:
##   current_focus:
##     - "backend/tests/test_password_reset.py"
##     - "backend/tests/test_client_portal.py"
##     - "backend/tests/test_atr_site_plan.py"
##     - "backend/tests/test_diu_doc_unit.py"
##     - "backend/tests/test_power_diu_sync.py"
##     - "backend/tests/test_pram_document_truthfulness.py"
##     - "backend/tests/test_atr_prefill_sheet.py"
##     - "backend/tests/test_atr_equipment_direct_catalog.py"
##     - "backend/tests/test_supplier_catalog.py"
##     - "backend/tests/test_anre_gdpr_consent_truthfulness.py"
##     - "backend/tests/test_anre_attestation_type_matching.py"
##     - "backend/tests/test_technical_parameter_safety.py"
##     - "backend/tests/test_cef_storage_truth.py"
##     - "backend/tests/test_cef_unknown_phases.py"
##     - "frontend/src/App.js and touched JSX files"
##   stuck_tasks:
##     - "Latest local changes are not deployed; Render's API last successful deploy is c072db2 and a later build for 2ad92a0 failed because workspace pipeline minutes were exhausted."
##     - "Full Vite build is unavailable because dependencies are absent from this checkout and the offline dependency link is denied."
##   test_all: false
##   test_priority: "high_first"
## agent_communication:
##   - agent: "main"
##     message: "Rebased the local work onto current origin/deployment-prep in a separate worktree; running focused helper, dossier, ATR, DIU, and frontend syntax checks. Full server/Mongo/SMTP integration and Render deploy remain to verify."
##   - agent: "main"
##     message: "Python compilation passed; 39 focused helper/document checks and 24 additional ANRE/technical checks passed. One PDF-to-image raster test was skipped because PyMuPDF is missing. Four test modules could not import because pytest/httpx/openai are missing. Babel parsed all seven touched frontend files. Render still serves c072db2; 2ad92a0 was cancelled after pipeline minutes were exhausted."
##   - agent: "main"
##     message: "Render MCP shows frontend commit 22bf944 is live, API commit c072db2 is live, and API commit 2ad92a0 failed because pipeline minutes are exhausted. Earlier direct smoke checks returned frontend HTTP 200 and API /readyz HTTP 200 with MongoDB ping ok; these verify the deployed versions only, not the current local integration."
##   - agent: "main"
##     message: "Compared the public WattEver manual against DNS source: DNS already has a three-step document-first dossier flow, live dashboard inbox/Kanban, equipment selection and DIU/ATR/ANRE/catalog/signing modules. Authenticated UI inspection was unavailable because browser control is disabled; no proprietary UI/source was copied."
