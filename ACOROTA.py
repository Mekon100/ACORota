import streamlit as st
import datetime
import pandas as pd
from calendar import monthrange
import random
import io

# ---------------------------
# Helper Functions
# ---------------------------

def generate_all_dates(year, month):
    """Generate a list of all dates for the given month."""
    _, num_days = monthrange(year, month)
    return [datetime.date(year, month, d) for d in range(1, num_days + 1)]

def generate_dates(year, month):
    """Generate only weekdays (Mon-Fri) for the given month."""
    _, num_days = monthrange(year, month)
    start_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month, num_days)
    dates = []
    for i in range((end_date - start_date).days + 1):
        d = start_date + datetime.timedelta(days=i)
        if d.weekday() < 5:  # Only Monday (0) to Friday (4)
            dates.append(d)
    return dates

def generate_rota(dates, staff, closure_days):
    """
    Generate a rota with one shift per day.
    Avoid assigning a staff member on consecutive working days if possible.
    Randomly choose among candidates with the same minimum shift count.
    Notes will include information on staff holidays.
    """
    rota_data = []
    last_assigned_staff = None  # Track the staff assigned on the previous working day.
    
    for date in dates:
        entry = {
            'Date': date.strftime('%d/%m/%Y'),
            'Day': date.strftime('%A'),
            'Shift': None,
            'Notes': ''
        }
        # Check for closure days.
        if date in closure_days:
            note = "University Closure"
            # Also note if any staff have a holiday on this day.
            holiday_names = [s['name'] for s in staff if date in s['holidays']]
            if holiday_names:
                note += " | On Holiday: " + ", ".join(holiday_names)
            entry['Notes'] = note
            entry['Shift'] = 'CLOSED'
            last_assigned_staff = None  # Reset consecutive assignment chain.
            rota_data.append(entry)
            continue

        weekday = date.weekday()
        # List staff available on this weekday,
        # not on holiday and not already assigned on that day.
        available_staff = [
            s for s in staff
            if weekday in s['office_days']
            and date not in s['holidays']
            and date not in s['assigned_dates']
        ]
        # Avoid the staff member who worked on the previous working day, if possible.
        if last_assigned_staff is not None:
            filtered = [s for s in available_staff if s['name'] != last_assigned_staff]
            if filtered:
                available_staff = filtered

        if not available_staff:
            # Fallback: allow back-to-back assignment if necessary.
            back_to_back_candidates = [
                s for s in staff
                if weekday in s['office_days'] and date not in s['holidays']
            ]
            if last_assigned_staff is not None:
                filtered = [s for s in back_to_back_candidates if s['name'] != last_assigned_staff]
                if filtered:
                    back_to_back_candidates = filtered
            if back_to_back_candidates:
                min_shifts = min(s['shift_count'] for s in back_to_back_candidates)
                candidates = [s for s in back_to_back_candidates if s['shift_count'] == min_shifts]
                selected = random.choice(candidates)
                entry['Shift'] = selected['name']
                selected['assigned_dates'].add(date)
                selected['shift_count'] += 1
                last_assigned_staff = selected['name']
            else:
                entry['Shift'] = 'UNASSIGNED'
                last_assigned_staff = None
        else:
            min_shifts = min(s['shift_count'] for s in available_staff)
            candidates = [s for s in available_staff if s['shift_count'] == min_shifts]
            selected = random.choice(candidates)
            entry['Shift'] = selected['name']
            selected['assigned_dates'].add(date)
            selected['shift_count'] += 1
            last_assigned_staff = selected['name']
        
        # Append holiday information to the notes for this date.
        holiday_names = [s['name'] for s in staff if date in s['holidays']]
        if holiday_names:
            if entry['Notes']:
                entry['Notes'] += " | On Holiday: " + ", ".join(holiday_names)
            else:
                entry['Notes'] = "On Holiday: " + ", ".join(holiday_names)
                
        rota_data.append(entry)
    return pd.DataFrame(rota_data)

def validate_shifts(df, staff):
    """Validate that no staff member is assigned on a holiday."""
    warnings = []
    for _, row in df.iterrows():
        try:
            date = datetime.datetime.strptime(row['Date'], '%d/%m/%Y').date()
        except ValueError:
            warnings.append(f"Invalid date format in {row['Date']}")
            continue
        for s in staff:
            if row['Shift'] == s['name'] and date in s['holidays']:
                warnings.append(f"{s['name']} assigned on holiday: {row['Date']}")
    return warnings

# ---------------------------
# Streamlit App Layout
# ---------------------------

st.title("Monthly Front Desk Rota Generator")

# Step 1: Select Target Month
st.header("1. Select Target Month")
target_date = st.date_input("Select any date in the target month", value=datetime.date.today())
year = target_date.year
month = target_date.month

# Generate all dates for the month (for holiday and closure selections)
all_dates = generate_all_dates(year, month)
all_date_strings = [d.strftime('%d/%m/%Y') for d in all_dates]

# Pre-defined staff list with office days.
# Office days: Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4.
staff_list = [
    {"name": "John",   "office_days": [1, 2, 4], "holidays": set(), "assigned_dates": set(), "shift_count": 0},  # Tuesday, Wednesday, Friday
    {"name": "Jane",   "office_days": [0, 1, 2], "holidays": set(), "assigned_dates": set(), "shift_count": 0},  # Monday, Tuesday, Wednesday
    {"name": "Cheryl", "office_days": [1, 2, 4], "holidays": set(), "assigned_dates": set(), "shift_count": 0},  # Tuesday, Wednesday, Friday
    {"name": "Claire", "office_days": [2, 3, 4], "holidays": set(), "assigned_dates": set(), "shift_count": 0},  # Wednesday, Thursday, Friday
    {"name": "Sarmad", "office_days": [0, 1, 3], "holidays": set(), "assigned_dates": set(), "shift_count": 0}   # Monday, Tuesday, Thursday
]

# Step 2: Staff Holidays
st.header("2. Staff Holidays")
st.write("For each staff member, select their holiday dates (if any) for the target month.")

# For each staff member, let the user select holiday dates.
for staff in staff_list:
    key = f"holidays_{staff['name']}"
    selected_holidays = st.multiselect(f"Holidays for {staff['name']}:", options=all_date_strings, key=key)
    # Convert the selected date strings to date objects.
    staff['holidays'] = {datetime.datetime.strptime(date_str, '%d/%m/%Y').date() for date_str in selected_holidays}

# Step 3: University Closure Days
st.header("3. University Closure Days")
closure_selected = st.multiselect("Select Closure Days (when the university is closed):", options=all_date_strings, key="closure_days")
closure_days = {datetime.datetime.strptime(date_str, '%d/%m/%Y').date() for date_str in closure_selected}

# Step 4: Generate Rota
st.header("4. Generate Rota")
if st.button("Generate Rota"):
    # Reset the assigned_dates and shift_count for each staff member.
    for s in staff_list:
        s['assigned_dates'] = set()
        s['shift_count'] = 0

    # Generate working dates (weekdays) for the target month.
    working_dates = generate_dates(year, month)
    rota_df = generate_rota(working_dates, staff_list, closure_days)
    warnings = validate_shifts(rota_df, staff_list)
    
    if warnings:
        st.warning("Warnings:")
        for w in warnings:
            st.text(w)
    else:
        st.success("No warnings found.")
    
    st.subheader("Rota Table")
    st.dataframe(rota_df)
    
    # Provide an Excel download button.
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        rota_df.to_excel(writer, index=False)
    output.seek(0)
    st.download_button("Download Rota as Excel", data=output, file_name="rota.xlsx", mime="application/vnd.ms-excel")
    
    # Display shift summary.
    st.subheader("Shift Summary")
    summary = [{'Name': s['name'], 'Shift Count': s['shift_count']} for s in staff_list]
    summary_df = pd.DataFrame(summary)
    st.dataframe(summary_df)
