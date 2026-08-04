import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    anchors.fill: parent
    spacing: Theme.gap

    Text {
        text: "Your cart"
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.titleFontPx
        font.bold: true
        Layout.fillWidth: true
    }

    ListView {
        id: list
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        model: CartModel
        spacing: Theme.gap
        boundsBehavior: Flickable.StopAtBounds

        delegate: CartLineItem {
            width: list.width
            name: model.name
            quantity: model.quantity
            lineTotalText: model.lineTotalText
        }

        EmptyState {
            anchors.centerIn: parent
            visible: list.count === 0
            message: "Your cart is empty"
        }
    }

    PriceDisplay {
        amount: App.cartTotalText
        Layout.fillWidth: true
    }

    BottomActionBar {
        Layout.fillWidth: true
        SecondaryButton {
            text: "Continue shopping"
            Layout.fillWidth: true
            onClicked: App.enterBrowse()
        }
        PrimaryButton {
            text: "Checkout"
            success: true
            enabled: App.checkoutEnabled
            Layout.fillWidth: true
            onClicked: App.startCheckout()
        }
    }
}
