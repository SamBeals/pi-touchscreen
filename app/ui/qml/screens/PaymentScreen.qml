import QtQuick
import QtQuick.Layouts
import "../components"
import SellMate 1.0

ColumnLayout {
    id: root
    anchors.fill: parent
    spacing: Theme.sectionGap

    readonly property bool active: App.screen === "payment"
    readonly property bool showVendCountdown: App.vendWaitActive

    Item { Layout.fillHeight: true; Layout.preferredHeight: 2 }

    Item {
        Layout.alignment: Qt.AlignHCenter
        width: Theme.statusBadgeSize + 28
        height: Theme.statusBadgeSize + 28

        // Pulse ring while waiting on payment / indeterminate vend.
        Rectangle {
            id: pulseRing
            anchors.centerIn: parent
            width: Theme.statusBadgeSize + 8
            height: Theme.statusBadgeSize + 8
            radius: width / 2
            color: "transparent"
            border.width: 3
            border.color: Theme.primary
            opacity: root.active && !root.showVendCountdown ? 0.55 : 0
            visible: opacity > 0.01

            SequentialAnimation on scale {
                running: root.active && !root.showVendCountdown && Theme.animationMs > 0
                loops: Animation.Infinite
                NumberAnimation { from: 0.92; to: 1.12; duration: Math.max(500, Theme.animationMs * 4); easing.type: Easing.InOutQuad }
                NumberAnimation { from: 1.12; to: 0.92; duration: Math.max(500, Theme.animationMs * 4); easing.type: Easing.InOutQuad }
            }
            SequentialAnimation on opacity {
                running: root.active && !root.showVendCountdown && Theme.animationMs > 0
                loops: Animation.Infinite
                NumberAnimation { from: 0.55; to: 0.15; duration: Math.max(500, Theme.animationMs * 4) }
                NumberAnimation { from: 0.15; to: 0.55; duration: Math.max(500, Theme.animationMs * 4) }
            }
        }

        // Determinate remaining-time ring while AUTHORIZED (waiting to vend).
        Canvas {
            id: waitRing
            anchors.centerIn: parent
            width: Theme.statusBadgeSize + 8
            height: Theme.statusBadgeSize + 8
            visible: root.showVendCountdown
            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                var cx = width / 2
                var cy = height / 2
                var r = Math.min(width, height) / 2 - 3
                ctx.lineWidth = 4
                ctx.strokeStyle = Theme.border
                ctx.beginPath()
                ctx.arc(cx, cy, r, 0, Math.PI * 2)
                ctx.stroke()
                ctx.strokeStyle = Theme.primary
                ctx.beginPath()
                var start = -Math.PI / 2
                var sweep = Math.PI * 2 * Math.max(0, Math.min(1, App.vendWaitProgress))
                ctx.arc(cx, cy, r, start, start + sweep)
                ctx.stroke()
            }
            Connections {
                target: App
                function onStatusChanged() { waitRing.requestPaint() }
            }
        }

        Rectangle {
            anchors.centerIn: parent
            width: Theme.statusBadgeSize
            height: Theme.statusBadgeSize
            radius: width / 2
            color: Theme.secondary
            border.color: Theme.border
            border.width: 1

            // Card glyph (hidden during countdown — show seconds instead)
            Rectangle {
                anchors.centerIn: parent
                width: Theme.statusBadgeSize * 0.52
                height: Theme.statusBadgeSize * 0.34
                radius: Theme.squareRadius
                color: Theme.primary
                visible: !root.showVendCountdown

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.topMargin: parent.height * 0.28
                    height: Math.max(3, parent.height * 0.12)
                    color: Theme.text
                    opacity: 0.22
                }
            }

            Text {
                anchors.centerIn: parent
                visible: root.showVendCountdown
                text: String(App.vendWaitSecondsRemaining)
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.statusBadgeSize * 0.36
                font.bold: true
            }
        }
    }

    PaymentStatusPanel {
        title: "Payment"
        message: App.paymentMessage
        Layout.fillWidth: true
    }

    Text {
        visible: root.showVendCountdown
        text: App.vendWaitSecondsRemaining + "s left before payment is cancelled"
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.subtitleFontPx
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }

    // Thin progress bar under countdown copy.
    Rectangle {
        visible: root.showVendCountdown
        Layout.fillWidth: true
        Layout.preferredHeight: 8
        radius: 4
        color: Theme.border

        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: parent.width * App.vendWaitProgress
            radius: parent.radius
            color: Theme.primary
            Behavior on width {
                NumberAnimation {
                    duration: Math.max(80, Theme.animationMs)
                    easing.type: Easing.OutQuad
                }
            }
        }
    }

    Item { Layout.fillHeight: true; Layout.preferredHeight: 3 }

    PrimaryButton {
        text: "Cancel purchase"
        danger: true
        visible: App.cancelEnabled
        Layout.fillWidth: true
        onClicked: App.cancelCheckout()
    }

    // After AUTHORIZED/VENDING, Cloud cancel is unsafe for the user button.
    // Wait-timeout cancel is automatic. Back to home is local escape only.
    SecondaryButton {
        text: "Back to home"
        visible: !App.cancelEnabled
        Layout.fillWidth: true
        onClicked: App.abandonActiveOrder()
    }
}
