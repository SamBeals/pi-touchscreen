import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    property string title: ""
    property bool showCart: false
    spacing: Theme.gap
    Layout.fillWidth: true

    Text {
        text: root.title
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.titleFontPx
        font.bold: true
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }

    PrimaryButton {
        visible: root.showCart
        text: "Cart (" + App.cartCount + ")"
        Layout.fillWidth: true
        onClicked: App.openCart()
    }
}
