import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    anchors.fill: parent
    spacing: Theme.sectionGap

    Item { Layout.fillHeight: true; Layout.preferredHeight: 2 }

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
