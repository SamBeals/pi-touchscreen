import QtQuick
import QtQuick.Layouts
import "../components"
import SellMate 1.0

ColumnLayout {
    anchors.fill: parent
    spacing: Theme.gap

    AppHeader {
        showBrand: false
        title: "Your cart"
        showCart: false
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

    ElevatedCard {
        Layout.fillWidth: true
        implicitHeight: totalCol.implicitHeight + 28

        ColumnLayout {
            id: totalCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins: 18
            spacing: 4

            Text {
                text: "Total"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodyFontPx
            }

            PriceDisplay {
                amount: App.cartTotalText.replace(/^Total:\s*/, "")
                Layout.fillWidth: true
            }
        }
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
            enabled: App.checkoutEnabled
            Layout.fillWidth: true
            onClicked: App.startCheckout()
        }
    }
}
