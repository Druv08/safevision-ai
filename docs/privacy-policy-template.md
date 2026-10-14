# SafeVision AI: privacy and usage policy template

A starting point for a site that runs SafeVision AI. It has four parts you can
adapt and publish:

1. [Monitoring notice](#1-monitoring-notice) for workers and visitors (induction pack, notice board)
2. [Signage text](#2-signage-text) for the camera areas, in English and Hindi
3. [Retention statement](#3-retention-statement)
4. [Usage policy: coaching, not punishment](#4-usage-policy-coaching-not-punishment) for supervisors and managers

**How to use it.** Replace everything in `[square brackets]`. Make the numbers
match your backend settings (see the [table at the end](#5-keep-the-text-and-the-settings-in-step));
if you change a setting, change the text too. Have it reviewed by whoever
handles legal and HR matters for the site, and by worker representatives where
there are any. This template is not legal advice, and using it does not by
itself make a deployment lawful: data protection rules (for example India's
Digital Personal Data Protection Act 2023, or the GDPR for sites in the EU)
and labour law may require more, such as a documented purpose, a named
contact or consultation before cameras are switched on.

**Wording.** Describe the system as **PPE presence detection**, not "PPE
compliance" monitoring. The software reports whether it *saw* a helmet or a
vest on a person in a camera frame. It cannot tell whether someone was
required to wear one, whether PPE was issued, or why it was missing, and it
makes mistakes. Only a person reviewing the record can decide that.

---

## 1. Monitoring notice

> **PPE presence detection at [site name]**
>
> **What we do.** Cameras at [areas, e.g. the north gate, scaffold zone B]
> are connected to SafeVision AI, a system that checks whether a hard hat and
> a high-visibility vest can be seen on people in [these areas]. Some areas
> are marked as no-entry; the system also notes when someone is seen inside
> one.
>
> **Why.** To prevent head injuries and vehicle strikes, and to find where
> PPE, training or site layout needs to improve. The system is used for
> safety coaching, not to punish anyone (see our usage policy).
>
> **What is recorded.** When the system does not see a required item on a
> person for about [2] seconds, it saves one record: the time, the camera
> and zone, what was not detected, and one still image. In that image every
> detected person, faces included, is pixelated so they cannot be
> recognised. Video is not recorded. The system does not use face
> recognition and does not identify anyone by name.
>
> **Who sees it.** [Site safety supervisors and the HSE manager.] A
> supervisor [may receive a WhatsApp message or another alert] when a record
> is made. The message contains no image.
>
> **Unblurred images.** For [72 hours] an encrypted copy of the image without
> pixelation is kept, so that a disputed record can be checked. Only [named
> roles, e.g. the HSE manager] can open it, and every opening is logged with
> their name and the time.
>
> **How long we keep it.** Images are deleted after [30 days]. Records without
> images are kept [for statistics / for N months]. Records may be kept longer
> only when required for an incident investigation, an insurance claim or a
> legal process ("legal hold").
>
> **Mistakes happen.** The system can miss PPE that is worn, or see PPE that
> is not there. No action is taken on a record until a person has reviewed it.
>
> **Your rights.** You can ask [contact] whether a record about you exists, see
> it, and dispute it. [Add any other rights that apply where you are, e.g.
> correction, erasure, complaint to a regulator.]
>
> **Questions:** [name, role, phone, email].

## 2. Signage text

Post at the entrance to each monitored area, at eye level, large enough to read
from [3] metres. Keep the English and Hindi together.

**English**

> **CAMERAS IN USE: PPE presence detection**
>
> Cameras here check whether a hard hat and a hi-vis vest can be seen.
> For safety and training, not punishment.
> People in saved images are blurred. Images are deleted after [30] days.
> No face recognition.
>
> Questions: [name, phone]

**हिन्दी (Hindi)**

> **इस क्षेत्र में कैमरे लगे हैं: PPE उपस्थिति पहचान**
>
> ये कैमरे जाँचते हैं कि हेलमेट और हाई-विज़ सेफ़्टी वेस्ट दिख रहे हैं या नहीं।
> उद्देश्य सुरक्षा और प्रशिक्षण है, सज़ा नहीं।
> सेव की गई तस्वीरों में लोग धुंधले किए जाते हैं। तस्वीरें [30] दिन बाद मिटा दी जाती हैं।
> चेहरा पहचान (फ़ेस रिकग्निशन) का उपयोग नहीं होता।
>
> प्रश्न: [नाम, फ़ोन]

For a no-entry zone add:

> **No entry: a person in this area is recorded as a zone intrusion.**
> **प्रवेश वर्जित: इस क्षेत्र में किसी व्यक्ति के दिखने पर उसे रिकॉर्ड किया जाता है।**

Have the Hindi checked by a native speaker on site; add other languages your
workforce uses.

## 3. Retention statement

> **Retention of PPE presence detection data at [site name]**
>
> | Data | Kept for | Then |
> |---|---|---|
> | Still image with people pixelated | [30] days from capture | Deleted automatically. The record stays without the image. |
> | Encrypted unblurred copy of that image | [72] hours from capture | Deleted automatically. |
> | Record without image (time, camera, zone, type, review status, cause, note) | [period, e.g. 24 months] | [Deleted / anonymised by an administrator.] |
> | Uploaded photos and videos (for analysis) | Deleted straight after analysis; any left behind by an error are deleted after [30] days | Deleted automatically. |
> | Alert delivery log (who was alerted, when) | [period] | [Deleted by an administrator.] |
> | Audit log (who viewed, exported, changed or deleted a record) | [period, e.g. 6 years] | Cannot be edited or deleted through the system. |
>
> **Legal hold.** An administrator can place a record on legal hold, with a
> written reason, when it is needed for an incident investigation, an
> insurance claim or a legal process. A held record keeps its image and its
> unblurred copy and cannot be deleted until the hold is released; placing
> and releasing a hold are both logged. Holds are reviewed [every 3 months].
>
> **Integrity.** Each image's SHA-256 fingerprint is stored when it is
> captured, so anyone can later check that an exported image has not been
> altered.

## 4. Usage policy: coaching, not punishment

> **How [company] uses PPE presence detection**
>
> 1. **Purpose.** The system exists to reduce injuries. It is used to find
>    where people are not protected and to fix the reason: missing stock,
>    the wrong size, an unclear zone, a gap in training. It is not used to
>    measure productivity, attendance or time keeping, or for any purpose
>    other than safety.
> 2. **A record is a prompt, not proof.** It shows that the camera did not see
>    an item. Before acting, a supervisor reviews the record and, where
>    possible, speaks to the person and checks the situation on site.
> 3. **First response is coaching.** The response to a record is a
>    conversation, a briefing or getting the person the right PPE. Records
>    are not used on their own as grounds for warnings, deductions or other
>    disciplinary action. [If your site's disciplinary procedure can be
>    triggered by repeated, deliberate and *independently confirmed* unsafe
>    behaviour, say so here, and say that the system's records are never the
>    only evidence.]
> 4. **Fix the site's part first.** When a reviewer records the cause as
>    **"PPE not issued"**, that is a supply failure for the site to fix, not
>    the worker's fault. The weekly report shows these separately.
> 5. **Record what was done.** Each record is acknowledged, marked "action
>    taken" with a short note of what was done (for example "issued helmet,
>    size L; briefed crew"), and then closed. Notes describe actions, not
>    judgements about people.
> 6. **Aggregates, not league tables.** Reporting is by zone, shift and type.
>    Individuals are not ranked, named in reports, or compared with each
>    other.
> 7. **Unblurred images are the exception.** They are opened only to settle a
>    disputed record, by [roles], and every opening is logged. They are never
>    exported, shared or shown in meetings.
> 8. **Access is limited and logged.** Only [roles] have accounts. Viewing an
>    image, exporting evidence, changing a record and deleting it are all
>    written to an audit log that cannot be edited. [Role] reviews the audit
>    log [monthly].
> 9. **Workers can ask and dispute.** Anyone can ask to see records about
>    them and dispute them with [contact]. A disputed record is marked
>    "False detection" if the review agrees, and is not held against anyone.
> 10. **Review.** This policy, the camera positions and the zone rules are
>     reviewed [every 12 months] with [worker representatives / the safety
>     committee], and whenever the system is changed.

## 5. Keep the text and the settings in step

The bracketed numbers above are backend settings (`backend/.env`):

| Text | Setting | Default |
|---|---|---|
| Seconds before a record is made | `VIOLATION_WINDOW_SECONDS` | 2 |
| Images deleted after | `RETENTION_DAYS` | 30 |
| Unblurred copy kept for | `ORIGINAL_RETENTION_HOURS` (0 = never kept) | 72 |
| Unblurred copies kept at all | `EVIDENCE_SECRET_KEY` (empty = never kept) | empty |
| People pixelated in images | `PRIVACY_BLUR` | true |
| How often the deletion job runs | `RETENTION_INTERVAL_MINUTES` | 60 |
| Alert messages | alert recipients (Alerts page) and `ALERT_SOURCES` | camera |

What the software does **not** do, so the text must not promise it:

- Records without images, the alert log and the audit log are **not**
  deleted automatically. If your retention statement gives them a period,
  someone has to delete them (the audit log cannot be deleted through the
  application at all: that needs a database administrator).
- Pixelation covers only people the model **detected**. Someone it missed
  (partly hidden, far away, unusual pose) is not blurred.
- The software does not check that recipients have agreed to WhatsApp
  messages. Get that agreement when you add them.
