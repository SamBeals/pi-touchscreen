import QtQuick
import QtQuick.Layouts
import "../components"
import SellMate 1.0

ColumnLayout {
    id: root
    anchors.fill: parent
    spacing: Theme.sectionGap

    readonly property bool active: App.screen === "payment"

    Item { Layout.fillHeight: true; Layout.preferredHeight: 2 }

    Item {
        Layout.alignment: Qt.AlignHCenter
        width: Theme.statusBadgeSize + 28
        height: Theme.statusBadgeSize + 28

        // Pulse ring while waiting on payment.
        Rectangle {
            id: pulseRing
            anchors.centerIn: parent
            width: Theme.statusBadgeSize + 8
            height: Theme.statusBadgeSize + 8
            radius: width / 2
            color: "transparent"
            border.width: 3
            border.color: Theme.primary
            opacity: root.active ? 0.55 : 0

            SequentialAnimation on scale {
                running: root.active && Theme.animationMs > 0
                loops: Animation.Infinite
                NumberAnimation { from: 0.92; to: 1.12; duration: Math.max(500, Theme.animationMs * 4); easing.type: Easing.InOutQuad }
                NumberAnimation { from: 1.12; to: 0.92; duration: Math.max(500, Theme.animationMs * 4); easing.type: Easing.InOutQuad }
            }
            SequentialAnimation on opacity {
                running: root.active && Theme.animationMs > 0
                loops: Animation.Infinite
                NumberAnimation { from: 0.55; to: 0.15; duration: Math.max(500, Theme.animationMs * 4) }
                NumberAnimation { from: 0.15; to: 0.55; duration: Math.max(500, Theme.animationMs * 4) }
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

            // Card glyph
            Rectangle {
                anchors.centerIn: parent
                width: Theme.statusBadgeSize * 0.52
                height: Theme.statusBadgeSize * 0.34
                radius: Theme.squareRadius
                color: Theme.primary

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
        }
    }

    PaymentStatusPanel {
        title: "Payment"
        message: App.paymentMessage
        Layout.fillWidth: true
    }

    Item { Layout.fillHeight: true; Layout.preferredHeight: 3 }

    PrimaryButton {
        text: "Cancel purchase"
        danger: true
        enabled: App.cancelEnabled
        Layout.fillWidth: true
        onClicked: App.cancelCheckout()
    }
}
