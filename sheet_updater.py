import os.path
import os
from dotenv import load_dotenv
import json
from itertools import chain
import copy
from dateutil import parser

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')

def transform_json_to_sheet_data(data_for_sheet):
    """
    Transforms one SIG's data block into a 2D list for Google Sheets.
    """
    timestamps = sorted(list(data_for_sheet.keys()), key=parser.parse, reverse=True)
    all_ids = list(chain.from_iterable(data_for_sheet.values()))
    unique_ids = sorted(list(set(all_ids)))

    header_row = ["ID"] + timestamps
    data_rows = []
    
    for user_id in unique_ids:
        row = [user_id]
        for timestamp in timestamps:
            if user_id in data_for_sheet[timestamp]:
                row.append("here") # <-- CHANGED
            else:
                row.append("not here") # <-- CHANGED
        data_rows.append(row)

    sheet_data = [header_row] + data_rows
    return sheet_data

def convert_to_row_data(sheet_data):
    """
    Converts a simple list-of-lists into the RowData format
    required by the spreadsheets.batchUpdate 'updateCells' request.
    """
    rows_payload = []
    for row in sheet_data:
        cells = []
        for cell_value in row:
            cells.append({
                'userEnteredValue': {
                    'stringValue': str(cell_value)
                }
            })
        rows_payload.append({'values': cells})
    return rows_payload

def transform_for_all_sigs(json_data):
    """
    Transforms the entire JSON into a single 2D list for the 'All Sigs'
    sheet, stacked horizontally.
    """
    
    # 1. Get the union of all unique IDs
    all_id_lists = []
    for sig_data in json_data.values():
        all_id_lists.extend(sig_data.values())
    all_unique_ids = sorted(list(set(chain.from_iterable(all_id_lists))))

    # 2. Create the two-row header
    header_row_1 = ["ID"]
    header_row_2 = [""]
    ordered_sigs = sorted(json_data.keys())
    timestamp_map = {} 

    for sig_name in ordered_sigs:
        sig_data = json_data[sig_name]
        timestamps = sorted(list(sig_data.keys()), key=parser.parse, reverse=True)
        timestamp_map[sig_name] = timestamps
        header_row_1.extend([sig_name] * len(timestamps))
        header_row_2.extend(timestamps)

    # 3. Create the Data Rows
    data_rows = []
    for user_id in all_unique_ids:
        row = [user_id]
        for sig_name in ordered_sigs:
            sig_data = json_data[sig_name]
            timestamps = timestamp_map[sig_name]
            
            for ts in timestamps:
                if user_id in sig_data.get(ts, []):
                    row.append("here") # <-- CHANGED
                else:
                    row.append("not here") # <-- CHANGED
        data_rows.append(row)
            
    all_sigs_sheet_data = [header_row_1, header_row_2] + data_rows
    return all_sigs_sheet_data, ordered_sigs, timestamp_map

def update_sheet():
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token2.json"):
        creds = Credentials.from_authorized_user_file("token2.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token2.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("sheets", "v4", credentials=creds)
        
        with open("data/attendance.json") as f:
           json_data = json.load(f)

        # --- Assumed variables ---
        # service = build('sheets', 'v4', credentials=creds)
        # SPREADSHEET_ID = "YOUR_SPREADSHEET_ID"

        # -----------------------------------------------------
        # 1. PREPARE ALL DATA IN PYTHON FIRST
        # -----------------------------------------------------

        print("1. Transforming JSON data...")
        individual_sheet_data = {} # For 'admin', 'sig-hb', etc.
        for sheet_name, data_block in json_data.items():
            individual_sheet_data[sheet_name] = transform_json_to_sheet_data(data_block)

        # Run the new transformation for "All Sigs"
        all_sigs_data, ordered_sigs, ts_map = transform_for_all_sigs(json_data)


        # -----------------------------------------------------
        # 2. API CALL 1: Get existing, reset "All Sigs", and create missing
        # -----------------------------------------------------
        print("2. Sending API Call 1: Resetting 'All Sigs' and checking other sheets...")

        # This map will be populated with all final sheet IDs
        sheet_id_map = {} 

        # Define all the sheet names we *want* to exist
        # (Using individual_sheet_data from Step 1)
        desired_sheet_names = ["All Sigs"] + list(individual_sheet_data.keys())

        # We now track delete requests and add requests separately
        add_sheets_requests = []
        delete_sheets_requests = []

        # This list tracks the names of sheets we are *adding*
        # to map the API replies back to them.
        new_sheets_in_order = []

        try:
            # --- A: Get all existing sheets in the spreadsheet ---
            spreadsheet_meta = service.spreadsheets().get(
                spreadsheetId=SPREADSHEET_ID,
                fields='sheets(properties(title,sheetId))'
            ).execute()
            
            existing_sheets = {} # {title: sheetId}
            for sheet in spreadsheet_meta.get('sheets', []):
                props = sheet.get('properties', {})
                existing_sheets[props.get('title')] = props.get('sheetId')

            # --- B: Compare desired sheets vs. existing sheets ---
            for name in desired_sheet_names:
                
                # --- (NEW) Special handling for "All Sigs" ---
                if name == "All Sigs":
                    if name in existing_sheets:
                        # 1. Add request to DELETE the old "All Sigs" sheet
                        delete_sheets_requests.append({
                            'deleteSheet': {'sheetId': existing_sheets[name]}
                        })
                    
                    # 2. Add request to CREATE a new "All Sigs" sheet
                    add_sheets_requests.append({
                        'addSheet': {'properties': {'title': "All Sigs"}}
                    })
                    # 3. Track it so we can get its new ID from the reply
                    new_sheets_in_order.append("All Sigs")

                # --- Handling for all other individual SIG sheets ---
                else:
                    if name in existing_sheets:
                        # Sheet already exists, just save its ID. No reset.
                        sheet_id_map[name] = existing_sheets[name]
                    else:
                        # Sheet does NOT exist, add it to the request list
                        add_sheets_requests.append({
                            'addSheet': {'properties': {'title': name}}
                        })
                        # Keep track of the order we add them
                        new_sheets_in_order.append(name)

            # --- C: Combine requests and run the batchUpdate ---
            # We must run deletes *before* adds.
            all_requests = delete_sheets_requests + add_sheets_requests
            
            if all_requests:
                print(f"   ...Resetting 'All Sigs' and creating {len(new_sheets_in_order)-1} other new sheets.")
                
                batch_update_result = service.spreadsheets().batchUpdate(
                    spreadsheetId=SPREADSHEET_ID,
                    body={'requests': all_requests}
                ).execute()
                
                print("   ...Sheet reset/creation complete.")
                
                # --- D: Get the IDs of the sheets we *added* ---
                # The replies only correspond to the 'addSheet' requests.
                replies = batch_update_result.get('replies', [])
                
                # Find the 'addSheet' replies (some replies might be from 'deleteSheet')
                add_sheet_replies = [r['addSheet'] for r in replies if 'addSheet' in r]
                
                for i, add_reply in enumerate(add_sheet_replies):
                    # Get the name from the ordered list we built
                    sheet_name = new_sheets_in_order[i]
                    # Get the new ID from the reply
                    sheet_id_map[sheet_name] = add_reply['properties']['sheetId']
                    
            else:
                print("   ...All required sheets (except 'All Sigs') already exist.")

            # print(f"Final Sheet ID Map: {sheet_id_map}") # Optional: for debugging

        except Exception as e:
            print(f"Error during sheet check/creation: {e}")
            # Stop execution if we had an error
            exit()

        # -----------------------------------------------------
        # 3. API CALL 2: Write all data
        # -----------------------------------------------------
        print("3. Sending API Call 2: Writing data to all sheets...")

        data_to_write = []

        # A. Add data for individual sheets
        for sheet_name, data in individual_sheet_data.items():
            data_to_write.append({
                'range': f"'{sheet_name}'!A1",
                'values': data
            })

        # B. Add data for "All Sigs" sheet (now using the new data)
        data_to_write.append({
            'range': "'All Sigs'!A1",
            'values': all_sigs_data
        })

        data_write_body = {
            'valueInputOption': 'USER_ENTERED',
            'data': data_to_write
        }

        try:
            write_result = service.spreadsheets().values().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body=data_write_body
            ).execute()
            print("   ...Data written successfully.")
        except Exception as e:
            print(f"Error writing data: {e}")
            exit()

        # -----------------------------------------------------
        # 4. API CALL 3: Format All Sheets (Layout, Colors, & Width)
        # -----------------------------------------------------
        print("4. Sending API Call 3: Applying formatting...")

        formatting_requests = []
        all_sigs_sheet_id = sheet_id_map["All Sigs"]
        num_rows_in_all_sigs = len(all_sigs_data)
        num_cols_in_all_sigs = len(all_sigs_data[0]) if num_rows_in_all_sigs > 0 else 0

        # --- A. Define Colors and Formatting Rules ---
        green_bg = {'red': 0.85, 'green': 0.96, 'blue': 0.85} # A light green
        red_bg   = {'red': 0.96, 'green': 0.85, 'blue': 0.85} # A light red

        here_rule = {
            'addConditionalFormatRule': {
                'rule': {
                    'ranges': [], 
                    'booleanRule': {
                        'condition': {'type': 'TEXT_EQ', 'values': [{'userEnteredValue': 'here'}]},
                        'format': {'backgroundColor': green_bg}
                    }
                }, 'index': 0
            }
        }
        not_here_rule = {
            'addConditionalFormatRule': {
                'rule': {
                    'ranges': [],
                    'booleanRule': {
                        'condition': {'type': 'TEXT_EQ', 'values': [{'userEnteredValue': 'not here'}]},
                        'format': {'backgroundColor': red_bg}
                    }
                }, 'index': 0
            }
        }


        # --- B. Add Conditional Formatting for ALL sheets ---
        for sheet_name, sheet_id in sheet_id_map.items():
            start_row_index = 2 if sheet_name == "All Sigs" else 1
            rule_range = {'sheetId': sheet_id, 'startRowIndex': start_row_index, 'startColumnIndex': 0}
            
            rule1 = copy.deepcopy(here_rule)
            rule1['addConditionalFormatRule']['rule']['ranges'] = [rule_range]
            formatting_requests.append(rule1)
            
            rule2 = copy.deepcopy(not_here_rule)
            rule2['addConditionalFormatRule']['rule']['ranges'] = [rule_range]
            formatting_requests.append(rule2)

            
        # --- C. (NEW) Resize columns for ALL sheets ---
        new_width_px = 150 # 1.5x default width (100px)

        for sheet_name, sheet_id in sheet_id_map.items():
            
            # Determine the number of columns in this sheet
            num_cols = 0
            if sheet_name == "All Sigs":
                num_cols = num_cols_in_all_sigs
            elif sheet_name in individual_sheet_data:
                # Get col count from the individual sheet's data
                if individual_sheet_data[sheet_name]:
                    num_cols = len(individual_sheet_data[sheet_name][0])
                    
            # We only resize columns if there are more than 1 (col A + data)
            if num_cols > 1:
                formatting_requests.append({
                    'updateDimensionProperties': {
                        'range': {
                            'sheetId': sheet_id,
                            'dimension': 'COLUMNS',
                            'startIndex': 1, # Start from column B (index 1)
                            'endIndex': num_cols # Resize up to the last column
                        },
                        'properties': {
                            'pixelSize': new_width_px
                        },
                        'fields': 'pixelSize'
                    }
                })

                
        # --- D. Add "All Sigs" Layout Formatting ---
        # (This section was previously 'C')

        # 1. Unmerge all cells in the header rows
        if num_rows_in_all_sigs > 0:
            formatting_requests.append({
                'unmergeCells': {
                    'range': {
                        'sheetId': all_sigs_sheet_id,
                        'startRowIndex': 0, 'endRowIndex': 2,
                        'startColumnIndex': 0, 'endColumnIndex': num_cols_in_all_sigs
                    }
                }
            })

        # 2. Center-align the two header rows
        formatting_requests.append({
            'repeatCell': {
                'range': {'sheetId': all_sigs_sheet_id, 'startRowIndex': 0, 'endRowIndex': 2},
                'cell': {'userEnteredFormat': {'horizontalAlignment': 'CENTER'}},
                'fields': 'userEnteredFormat.horizontalAlignment'
            }
        })

        # 3. Loop and apply new merges and borders
        thick_border = {'style': 'SOLID_THICK', 'color': {'red': 0.0, 'green': 0.0, 'blue': 0.0}}
        current_col_index = 1 # Start at column B

        for sig_name in ordered_sigs:
            num_cols = len(ts_map[sig_name])
            if num_cols == 0: continue

            # Merge top-level SIG name cell
            if num_cols > 1:
                formatting_requests.append({
                    'mergeCells': {
                        'range': {
                            'sheetId': all_sigs_sheet_id,
                            'startRowIndex': 0, 'endRowIndex': 1,
                            'startColumnIndex': current_col_index,
                            'endColumnIndex': current_col_index + num_cols
                        }, 'mergeType': 'MERGE_ALL'
                    }
                })

            # Add thick left border
            formatting_requests.append({
                'updateBorders': {
                    'range': {
                        'sheetId': all_sigs_sheet_id,
                        'startRowIndex': 0, 'endRowIndex': num_rows_in_all_sigs,
                        'startColumnIndex': current_col_index, 'endColumnIndex': current_col_index + 1
                    }, 'left': thick_border
                }
            })
            current_col_index += num_cols

        # 4. Add one final thick border to the right
        formatting_requests.append({
            'updateBorders': {
                'range': {
                    'sheetId': all_sigs_sheet_id,
                    'startRowIndex': 0, 'endRowIndex': num_rows_in_all_sigs,
                    'startColumnIndex': current_col_index - 1, 'endColumnIndex': current_col_index
                }, 'right': thick_border 
            }
        })

        # --- E. Execute the Batch Update ---
        # (This section was previously 'D')
        try:
            if formatting_requests:
                format_result = service.spreadsheets().batchUpdate(
                    spreadsheetId=SPREADSHEET_ID,
                    body={'requests': formatting_requests}
                ).execute()
                print("   ...Formatting and column sizing applied successfully.")
            else:
                print("   ...No formatting requests to apply.")
                
            print("\n✅ All operations complete.")

        except Exception as e:
            print(f"Error applying formatting: {e}")
    except HttpError as err:
        print(err)


# if __name__ == "__main__":
#     update_sheet()
