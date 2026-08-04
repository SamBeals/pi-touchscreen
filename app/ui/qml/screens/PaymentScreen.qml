import QtQuick
import QtQuick.Layouts
import "../components"
import SellMate 1.0

ColumnLayout {
    anchors.fill: parent
    spacing: Theme.sectionGap

    Item { Layout.fillHeight: true; Layout.preferredHeight: 2 }

    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        width: Theme.statusBadgeSize + 16
        height: Theme.statusBadgeSize + 16
        radius: (Theme.statusBadgeSize + 16) / 2
        color: Theme.secondary

        Rectangle {
            anchors.centerIn: parent
            width: Theme.statusBadgeSize / 2 + 8
            height: 30
            radius: Theme.squareRadius - 2
            color: Theme.primary
            border.color: Theme.text
            border.width: 0

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.topMargin: 8
                height: 4
                color: Theme.text
                opacity: 0.25
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
