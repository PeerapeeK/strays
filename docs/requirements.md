# Project Handover Document: Stray Dog Adoption and Owner Screening System (ระบบหาบ้านและคัดกรองเจ้าของให้สุนัขจรจัด)

## 1. Project Overview
* **Project Name:** Stray Dog Adoption and Owner Screening System (ระบบหาบ้านและคัดกรองเจ้าของให้สุนัขจรจัด)
* **Team:** Group 8 (Section 1)
* **Student IDs:** 6887007, 6887032, 6887039, 6887042, 6887066
* **System Purpose:** An end-to-end information system for managing stray dog adoptions, including dog and health record management, public listing of adoptable dogs, adoption request processing, applicant evaluation, interview & home visit scheduling, contract management, post-adoption monitoring, and statistical reporting.
* **External Links & Architecture References:**
  * Draw.io Diagram Link: [System Diagram](https://app.diagrams.net/#G1MiUE3rCSYLbAZbrVt9fnvd44LhPzrpjQ#%7B%22pageld%22%3A%22iHz7KzINUXjNcqwkMAYY%22%7D)
  * Google Drive Reference: [Drive Link](https://drive.google.com/file/d/1_508j_nqtqWvEUrUbGsw4AN3Yvk2j5AY/view?usp=sharing)

---

## 2. System Actors & Responsibilities

### 2.1 Adopter (ผู้รับอุปการะสุนัข)
* **Account & Profile:** Account creation, login, filling out personal details, attaching housing photos, completing initial screening assessment.
* **Dog Management:** Search and inspect adoptable stray dog details.
* **Interview Appointments:** Book interview queue, check appointment status, cancel appointment, confirm interview attendance, receive push notifications (confirmation/rejection, upcoming reminders).
* **Contracts & Follow-ups:** Review adoption contract, attach housing photos in follow-up forms on schedule, request home visit rescheduling, receive follow-up photo reminders and home visit date notifications.

### 2.2 Shelter Staff (เจ้าหน้าที่ศูนย์รับเลี้ยง)
* **Authentication:** Login to the system.
* **Dog Management:** Create, search, inspect, and update stray dog records.
* **Interview Management:** Check requests, confirm/reject interviews, record interview results, attach interview photos.
* **Contract Management:** Create, inspect, save, and update adoption contracts.
* **Adoption Monitoring:** Schedule and modify home visit appointments, inspect and record data in follow-up forms, evaluate housing and dog conditions, attach follow-up photos, view adoption statistics reports. Receive push notifications for home visit dates.

### 2.3 System Administrator (ผู้ดูแลระบบ)
* **Authentication:** Login to the system.
* **User Management:** Create shelter staff accounts, modify user account details, suspend user accounts.
* **System Data:** Modify basic shelter configuration data.

### 2.4 External Actor
* **Push Notification Service Provider:** Handles dispatching push notifications.

---

## 3. Functional Requirements Summary

### Adopter Functions:
1. Create account & Login (FR 1, 2)
2. Search & inspect stray dogs (FR 3, 4)
3. Fill personal data, attach housing photo, complete initial assessment (FR 8, 9, 10)
4. Book, check, cancel, and confirm interview appointments (FR 5, 6, 7, 14)
5. Receive interview codes and push notifications (FR 11, 12, 13, 15)
6. Review adoption contract (FR 28)
7. Request home visit rescheduling (FR 38)
8. Attach housing photos in follow-up forms on schedule (FR 32), receive push reminders (FR 33)

### Shelter Staff Functions:
9. Login (FR 16)
10. Search, inspect, save, and modify stray dog data (FR 17, 18, 19, 20)
11. Check, confirm/reject interview appointments (FR 21, 22, 23)
12. Record interview results & attach photos (FR 24, 25)
13. Create, inspect, save, and modify adoption contracts (FR 26, 27, 29, 30)
14. Create and modify home visit appointments (FR 34, 35), trigger notifications (FR 36, 37)
15. Inspect and record follow-up forms, housing/dog condition details, and follow-up photos (FR 39, 40, 41, 42, 43)
16. Generate adoption and post-adoption follow-up statistical reports (FR 44, 45)

### Admin Functions:
17. Login (FR 48)
18. Create staff accounts, modify accounts, suspend accounts (FR 49, 50, 51)
19. Inspect adoption and follow-up statistical reports (FR 46, 47)

---

## 4. Non-Functional Requirements (NFR)
1. **Browser Support:** Compatible with latest versions of Chrome, Safari, and Edge.
2. **Responsive Design:** Supports all screen sizes (desktop, tablet, smartphone - iOS & Android) via web browsers.
3. **Usability:** Conforms to ISO 9241-11 standard, measured via System Usability Scale (SUS) score $\ge 60$.
4. **Concurrency:** Supports at least 1,000 concurrent users without violating response time rules.
5. **Response Time:** Responds to all user requests within 3 seconds.
6. **Availability:** Uptime $\ge 99.5\%$ per month.
7. **Security:** User passwords must be hashed using the **Argon2** algorithm.
8. **Privacy (PDPA):** Must obtain user consent prior to collecting personal data (personal info, housing photos, assessment results).
9. **Push Notification SLA:** Dispatch push requests to service provider within 1 minute of triggering event; automated retry system with at least 3 retries on failure.
10. **Audit Logging:** Traceability required for all data changes (who did what and when).

---

## 5. Core Use Case Narratives Summary

### Use Case 1: Book Interview Queue (จองคิวเพื่อนัดสัมภาษณ์)
* **Actor:** Adopter
* **Flow:** Login $\rightarrow$ Search & select adoptable dog $\rightarrow$ Select "Book Interview" $\rightarrow$ Fill personal details $\rightarrow$ Attach housing photo $\rightarrow$ Complete initial assessment $\rightarrow$ Select date/time $\rightarrow$ Submit.
* **System Action:** Validates data, generates interview code, saves request, and displays the code.
* **Exception:** If incomplete data $\rightarrow$ error notification & resume filling.

### Use Case 2: Modify Stray Dog Information (เปลี่ยนแปลงข้อมูลสุนัขจรจัด)
* **Actor:** Shelter Staff
* **Flow:** Login $\rightarrow$ Select "Dog Management" menu $\rightarrow$ Search dog to edit $\rightarrow$ Modify data $\rightarrow$ Confirm.
* **System Action:** Saves changes and shows success message.
* **Exception:** If invalid format or missing data $\rightarrow$ error notification & correct before re-submitting.

### Use Case 3: Attach Photos in Follow-up Form (แนบภาพถ่ายในแบบฟอร์มติดตามผล)
* **Actor:** Adopter
* **Flow:** Login $\rightarrow$ Access assigned follow-up form $\rightarrow$ Select "Attach housing photo" $\rightarrow$ Upload photo $\rightarrow$ Submit.
* **System Action:** Saves photo into the follow-up form.
* **Exception:** If invalid file extension $\rightarrow$ error notification & re-upload valid file.

---

## 6. Guidelines for the AI Agent
When implementing, testing, or expanding this system, ensure:
* Strict compliance with PDPA consent rules during profile creation/assessment submission.
* Argon2 password hashing implementation.
* Robust error handling and file-type validation for image uploads (housing photos, interview photos, follow-up photos).
* Push notification retry mechanism integration.