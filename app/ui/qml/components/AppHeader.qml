import QtQuick
import QtQuick.Layouts
import SellMate 1.0

Item {
    id: root
    property string title: ""
    property bool showCart: false
    property bool showBrand: true
    implicitHeight: row.implicitHeight

    RowLayout {
        id: row
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: Theme.gap

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Text {
                visible: root.showBrand
                text: Theme.businessName
                color: Theme.primary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.titleFontPx
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            Text {
                visible: root.title.length > 0 && !root.showBrand
                text: root.title
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.titleFontPx - 4
                font.bold: true
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Text {
                visible: root.title.length > 0 && root.showBrand
                text: root.title
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodyFontPx
                Layout.fillWidth: true
            }
        }

        Rectangle {
            visible: root.showCart
            Layout.preferredHeight: Math.max(52, Theme.secondaryButtonMinHeight - 4)
            Layout.preferredWidth: Math.max(cartLabel.implicitWidth + 40, 110)
            radius: height / 2
            color: Theme.secondary
            border.color: Theme.border
            border.width: 1

            Text {
                id: cartLabel
                anchors.centerIn: parent
                text: "Cart · " + App.cartCount
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodyFontPx
                font.bold: true
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    App.bumpIdle()
                    App.openCart()
                }
            }
        }
    }
}
